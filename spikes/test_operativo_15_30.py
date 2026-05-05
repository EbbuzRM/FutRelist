"""Test operativo simulato - Golden Hours 15:30-18:15

QUI E' UNO SPIKE THROWAWAY - Codice non pulito, solo proof-of-concept!

Simula il passaggio del tempo dalle 15:30 alle 18:15 accelerando il tempo di 60x:
- 1 secondo reale = 60 secondi simulati
- Il bot pensa di essere nel range 15:30-18:15
- Il browser si aprirà e opererà normalmente

USO:
    python spikes/test_operativo_15_30.py

Il bot partirà subito (15:30 simulate) e opererà fino alle 18:15 simulate.
Per fermarlo prima: Ctrl+C.

WARNING: Il bot farà operazioni reali sul browser (navigazione, rilist, ecc.)
Assicurati che il login sia attivo e che sia sicuro fare test.
"""

import sys
import time
import threading
from datetime import datetime, timedelta

# Speed factor: 1 secondo reale = 60 secondi simulati
SPEED = 60


class SimulatedClock:
    """Orologio simulato che accelera il tempo"""

    def __init__(self, start_hour=15, start_minute=30):
        self.current = datetime(2026, 5, 5, start_hour, start_minute, 0)
        self.start = self.current
        self.end_time = datetime(2026, 5, 5, 18, 15, 0)

    def now(self):
        """Restituisce il tempo simulato corrente - da usare come datetime.now()"""
        return self.current

    def advance(self, real_seconds):
        """Avanza il tempo simulato basandosi sui secondi reali passati"""
        sim_seconds = real_seconds * SPEED
        self.current += timedelta(seconds=sim_seconds)

    def check_end(self):
        """Controlla se abbiamo raggiunto la fine della simulazione"""
        if self.current >= self.end_time:
            print(f"\n[SIM] ========================================")
            print(f"[SIM] Raggiunto 18:15 simulato. Tempo finale: {self.current}")
            print(f"[SIM] Durata simulata: {self.current - self.start}")
            print(f"[SIM] ========================================")
            return True
        return False


def create_fake_datetime(clock):
    """Crea un oggetto che simula datetime.datetime con ora simulata

    Poiché i moduli fanno `from datetime import datetime`,
    il nome `datetime` nel modulo è la classe datetime.datetime.
    Dobbiamo sostituirla con un oggetto che ha un metodo `now()`.
    """

    class FakeDateTime:
        """Simula datetime.datetime"""

        @staticmethod
        def now():
            return clock.now()

        @staticmethod
        def fromtimestamp(ts):
            return datetime.fromtimestamp(ts)

        @staticmethod
        def strptime(date_string, format):
            return datetime.strptime(date_string, format)

        # Aggiungi altri metodi statici se necessario
        @staticmethod
        def combine(date, time):
            return datetime.combine(date, time)

    # Copia gli attributi della classe datetime originale che potrebbero servire
    FakeDateTime.min = datetime.min
    FakeDateTime.max = datetime.max
    FakeDateTime.resolution = datetime.resolution

    return FakeDateTime


def simulated_main():
    """Esegue il bot con tempo accelerato"""

    # Crea l'orologio simulato
    clock = SimulatedClock(15, 30)

    print(f"[SIM] ========================================")
    print(f"[SIM] TEST OPERATIVO SIMULATO - GOLDEN HOURS")
    print(f"[SIM] ========================================")
    print(f"[SIM] Inizio simulazione: {clock.current}")
    print(f"[SIM] Fine simulazione: {clock.end_time}")
    print(f"[SIM] Speed factor: {SPEED}x (1s reale = {SPEED}s simulati)")
    print(f"[SIM] ========================================")

    # Crea il fake datetime
    fake_datetime = create_fake_datetime(clock)

    # Importa i moduli che usano datetime
    # NOTA: dobbiamo importarli PRIMA di patchare
    import logic.golden_hour
    import logic.relist_engine
    import browser.session_keeper

    # Salva i riferimenti originali per ripristinarli dopo
    original_refs = {
        'logic.golden_hour': logic.golden_hour.datetime,
        'logic.relist_engine': logic.relist_engine.datetime,
        'browser.session_keeper': browser.session_keeper.datetime,
    }

    print(f"[SIM] Patching datetime in {len(original_refs)} moduli...")

    # Patch dei moduli: sostituisci datetime con il nostro fake
    logic.golden_hour.datetime = fake_datetime
    logic.relist_engine.datetime = fake_datetime
    browser.session_keeper.datetime = fake_datetime

    # Verifica il patch
    test_now = logic.golden_hour.datetime.now()
    print(f"[SIM] Verifica patch: logic.golden_hour.datetime.now() = {test_now}")
    assert test_now == clock.now(), "Patch fallito!"

    # Override di time.sleep per accelerare il tempo
    original_sleep = time.sleep

    def fast_sleep(seconds):
        """Sleep accelerato: avanza il tempo simulato senza bloccare"""
        # Avanza il tempo simulato
        clock.advance(seconds)

        # Log se stiamo dormendo a lungo (debug)
        if seconds > 10:
            print(
                f"[SIM] Sleep accelerato: {seconds}s → {seconds * SPEED}s simulati"
            )
            print(f"[SIM] Tempo simulato ora: {clock.now()}")

        # Sleep molto breve per non bloccare il processo
        # Usiamo un approccio smart: più è lungo il sleep richiesto,
        # più breve dormiamo (ma con un minimo)
        if seconds < 1:
            real_sleep = 0.001  # 1ms
        elif seconds < 60:
            real_sleep = 0.01  # 10ms
        else:
            real_sleep = 0.05  # 50ms

        original_sleep(real_sleep)

        # Controlla se abbiamo raggiunto la fine
        if clock.check_end():
            print(f"[SIM] Fine simulazione raggiunta durante sleep.")
            # Alza un'eccezione per uscire dal bot
            raise SystemExit("Simulazione completata")

    # Applica il patch a time.sleep
    time.sleep = fast_sleep
    print(f"[SIM] time.sleep patchato con fast_sleep")

    # Patch anche threading.Event.wait per avanzare il clock simulato
    original_event_wait = threading.Event.wait

    def fake_event_wait(self, timeout=None):
        """Override di threading.Event.wait per avanzare il clock simulato"""
        if timeout is not None and timeout > 0:
            clock.advance(timeout)
            # Sleep molto breve per non bloccare
            original_sleep(0.001)
        return True  # Assume sempre che il timeout sia scaduto

    # Patch threading.Event.wait
    threading.Event.wait = fake_event_wait
    print(f"[SIM] threading.Event.wait patchato")

    # Ora importa e lancia il main
    # NOTA: dobbiamo importare main DOPO aver fatto i patch
    try:
        # Salva riferimento alla funzione PRIMA di re-importare il modulo
        from main import main as main_function
        
        print(f"[SIM] ======================================")
        print(f"[SIM] Avvio del bot con tempo simulato...")
        print(f"[SIM] Il browser si aprirà a breve.")
        print(f"[SIM] Per fermare: Ctrl+C")
        print(f"[SIM] ======================================")

        # Override time.sleep in main module too
        import main
        if hasattr(main, 'time'):
            main.time.sleep = fast_sleep

        # Chiama la funzione salvata, non il modulo!
        main_function()

    except SystemExit as e:
        if str(e) == "Simulazione completata":
            print(f"[SIM] Simulazione terminata con successo!")
        else:
            print(f"[SIM] Bot terminato: {e}")
    except KeyboardInterrupt:
        print(f"\n[SIM] Interruzione manuale (Ctrl+C)")
    except Exception as e:
        print(f"\n[SIM] Errore durante la simulazione: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Ripristina tutto
        print(f"\n[SIM] Ripristino riferimenti originali...")
        time.sleep = original_sleep
        threading.Event.wait = original_event_wait
        for module_path, original_dt in original_refs.items():
            if module_path == 'logic.golden_hour':
                logic.golden_hour.datetime = original_dt
            elif module_path == 'logic.relist_engine':
                logic.relist_engine.datetime = original_dt
            elif module_path == 'browser.session_keeper':
                browser.session_keeper.datetime = original_dt

        print(f"[SIM] Tempo simulato finale: {clock.now()}")
        print(f"[SIM] ========================================")
        print(f"[SIM] FINE TEST OPERATIVO")
        print(f"[SIM] ========================================")


if __name__ == "__main__":
    simulated_main()
