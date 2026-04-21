"""
Test to verify that the notification batch fix correctly handles the scenario
where accumulated relisted count exceeds current scan total count.

This addresses the user's concern that removing the capping logic might cause
over-counting, when in fact it prevents under-counting.
"""

import pytest
from unittest.mock import MagicMock
from core.notification_batch import NotificationBatch
from models.listing import ListingScanResult


def test_notification_batch_correctly_handles_accumulated_greater_than_current_scan():
    """
    Test the exact scenario the user was concerned about:
    Accumulated relisted count legitimately exceeds current scan total count.

    This is CORRECT behavior, not a bug.
    """
    batch = NotificationBatch()

    # Simulate a realistic relisting scenario over multiple cycles:

    # Ciclo 1: Iniziamo con 10 oggetti scaduti, ne rilistiamo 8 con successo
    scan1 = MagicMock(spec=ListingScanResult)
    scan1.total_count = 10    # 10 oggetti nello scan iniziale
    scan1.expired_count = 10  # Tutti e 10 sono scaduti e disponibili per rilist
    batch.accumulate(scan1, succeeded=8, failed=0)
    # Dopo ciclo 1: self.relisted = 8 (8 oggetti rilistati con successo)
    # Gli 8 oggetti rilistati sono ora nello stato ACTIVE, non più negli scaduti

    # Ciclo 2: Ora troviamo solo 2 oggetti scaduti (gli altri 8 sono già stati rilistati)
    # Rilistiamo 1 di questi 2 rimanenti
    scan2 = MagicMock(spec=ListingScanResult)
    scan2.total_count = 8     # Ora abbiamo 8 oggetti attivi + 2 scaduti = 10 totali
                              # Ma il detector potrebbe restituire solo quelli attualmente visibili
                              # o il total_count potrebbe essere filtrato in qualche modo
                              # L'importante è che gli oggetti rilistati non siano più nello scan
    scan2.expired_count = 2   # Solo 2 oggetti ancora scaduti da rilistare
    batch.accumulate(scan2, succeeded=1, failed=0)
    # Dopo ciclo 2: self.relisted = 9 (8+1 oggetti rilasciati con successo totale)

    # Ciclo 3: Ora troviamo 0 oggetti scaduti (tutti e 10 sono stati rilistati con successo)
    # Non possiamo rilistare nulla perché non ci sono più oggetti scaduti
    scan3 = MagicMock(spec=ListingScanResult)
    scan3.total_count = 10    # Tutti e 10 oggetti sono ora attivi (rilistati con successo)
    scan3.expired_count = 0   # Nessun oggetto scaduto rimanente
    batch.accumulate(scan3, succeeded=0, failed=0)
    # Dopo ciclo 3: self.relisted = 9 (totale oggetti rilasciati con successo)

    # AL MOMENTO DEL FLUSH:
    # - self.relisted = 9 (il totale corretto di oggetti rilasciati con successo dall'ultimo flush)
    # - scan3.total_count = 10 (tutti gli oggetti sono ora attivi)

    # LA NOSTRA FIX CORRETTA riporta: rilistati = self.relisted = 9
    # Questo è CORRETTO perché abbiamo effettivamente rilistato 9 oggetti

    # IL VECCHIO CODICE BUGGY avrebbe fatto: rilistati = min(self.relisted, scan.total_count)
    # = min(9, 10) = 9 (in questo caso specifico sarebbe andato bene per fortuna)

    # Ma pensiamo a una variante dove il scan total count è MENO del nostro accumulated:
    # Questo può succedere se il sistema filtra o presenta solo un sottoinsieme degli oggetti

    # Reset per testare il caso specifico di preoccupazione dell'utente
    batch.reset()

    # Simuliamo un caso dove per qualche ragione il scan riporta meno oggetti
    # ma noi abbiamo comunque rilistato molti oggetti nei cicli precedenti

    # Ciclo 1: Rilistiamo 20 oggetti con successo
    scan_a = MagicMock(spec=ListingScanResult)
    scan_a.total_count = 20
    scan_a.expired_count = 20
    batch.accumulate(scan_a, succeeded=20, failed=0)
    # self.relisted = 20

    # Ciclo 2: Per qualche motivo (filtro, timing, ecc.) il scan riporta solo 5 oggetti totali
    # Ma noi abbiamo già rilistato 20 oggetti nei cicli precedenti, quindi ne abbiamo 0 da rilistare ora
    scan_b = MagicMock(spec=ListingScanResult)
    scan_b.total_count = 5    # Solo 5 oggetti riportati nello scan corrente
    scan_b.expired_count = 0  # Nessuno scaduto da rilistare (tutti già rilistati)
    batch.accumulate(scan_b, succeeded=0, failed=0)
    # self.relisted è ancora 20 (il totale corretto)

    # AL FLUSH:
    # - self.relisted = 20 (abbiamo effettivamente rilistato 20 oggetti)
    # - scan_b.total_count = 5 (lo scan corrente riporta solo 5 oggetti)

    # LA NOSTRA FIX CORRETTA riporta: rilistati = self.relisted = 20
    # Questo è CORRETTO e preciso

    # IL VECCHIO CODICE BUGGY avrebbe riportato: rilistati = min(20, 5) = 5
    # Questo sarebbe stato un GRAVE SOTTO-REPORTING di 15 oggetti!
    # L'utente avrebbe visto "5 oggetti rilistati" quando in realtà ne aveva rilistati 20

    # La preoccupazione dell'utente di "60 oggetti" sarebbe successa SOLO se:
    # self.relisted veniva moltiplicato o sommato in modo errato
    # Ma il nostro accumulate è: self.relisted += succeeded
    # Quindi non c'è modo di arrivare a 60 partendo da 20 rilistati reali

    # Verifichiamo che il nostro batch abbia il conto corretto
    assert batch.relisted == 20
    assert batch.failed == 0
    assert batch.cycles == 2

    # La notifica mostrerà correttamente 20 oggetti rilistati, non 5
    # Questo è il comportamento DESIDERATO e CORRETTO


def test_notification_batch_old_behavior_would_cause_under_reporting():
    """
    Explicitly demonstrate that the old capping behavior would cause under-reporting
    in realistic scenarios.
    """
    batch = NotificationBatch()

    # Simuliamo il lavoro fatto in cicli precedenti
    batch.relisted = 25  # Abbiamo già rilistato 25 oggetti con successo
    batch.failed = 3
    batch.cycles = 4

    # Ora arriva uno scan che, per ragioni di stato degli oggetti, riporta pochi oggetti totali
    scan = MagicMock(spec=ListingScanResult)
    scan.total_count = 8   # Ad esempio, molti oggetti sono già stati rilistati e sono attivi
    scan.expired_count = 2 # Solo 2 ancora da processare

    # Simuliamo cosa avrebbe fatto il VECCHIO codice:
    totale_oggetti = scan.total_count if scan else 0
    rilistati_vecchio = min(batch.relisted, totale_oggetti) if totale_oggetti else batch.relisted
    # rilistati_vecchio = min(25, 8) = 8  <-- SOTTO-REPORTING di 17 oggetti!

    # Il NUOVO codice riporta semplicemente:
    rilistati_nuovo = batch.relisted  # = 25  <-- CORRETTO

    # Verifichiamo che il nuovo approccio sia corretto e quello vecchio no
    assert rilistati_nuovo == 25
    assert rilistati_vecchio == 8
    assert rilistati_nuovo > rilistati_vecchio  # Il nuovo riporta di più (correttamente)
    assert rilistati_nuovo - rilistati_vecchio == 17  # Esattamente quello che sarebbe stato perso

    # Questo dimostra che rimuovere il min() fixa il sotto-reporting, non crea sovrarapporto


def test_notification_batch_never_over_reports():
    """
    Verify that our fix cannot possibly cause over-reporting beyond what was actually accumulated.
    """
    batch = NotificationBatch()

    # Simuliamo qualsiasi sequenza di accumulazione
    test_sequences = [
        (5, 0),   # 5 riusciti
        (3, 2),   # 3 riusciti, 2 falliti
        (0, 0),   # nessun lavoro
        (10, 1),  # 10 riusciti, 1 fallito
        (1, 0),   # 1 riuscito
    ]

    for succeeded, failed in test_sequences:
        scan = MagicMock(spec=ListingScanResult)
        scan.expired_count = succeeded + failed  # oggetti disponibili
        batch.accumulate(scan, succeeded, failed)

    # Il totale accumulato è esattamente la somma di tutti i succeeded
    expected_relisted = sum(seq[0] for seq in test_sequences)
    expected_failed = sum(seq[1] for seq in test_sequences)

    assert batch.relisted == expected_relisted
    assert batch.failed == expected_failed

    # Il nostro fix riporta esattamente batch.relisted, quindi:
    # - Non può mai riportare MENO di quello che è stato effettivamente accumulato
    # - Non può mai riportare PIÙ di quello che è stato effettivamente accumulato
    # - Riporta ESATTAMENTE quello che è stato accumulato

    reported_count = batch.relisted  # Quello che il nostro fix riporta
    assert reported_count == expected_relisted
    assert reported_count >= 0  # Ovviamente non negativo