# FIFA 26 Auto-Relist Bot - Activity Log

---

[2026-04-13T11:30:00Z] PROCESSING state fix shipped:
- Nuovo enum ListingState.PROCESSING per item in limbo EA (scaduti ma visibili come "active" nel DOM)
- detector.py: riconoscimento "processing"/"elaborazion" → PROCESSING invece di UNKNOWN
- detector.py: Step 4 - logica is_processing che intercetta "Processing..." prima che section='active' li classifichi erroneamente come ACTIVE (questo era il bug principale dei 2 mancanti)
- detector.py: expired_count in Step 5 ora somma EXPIRED + PROCESSING
- main.py: safety net post-relist - se rimangono PROCESSING items, next_wait forzato a 15s invece di aspettare expiry normale
- Notification accumulator: aggiunto campo expired_detected che accumula scan.expired_count di tutti i cicli del batch
- _send_batch_notification: usa accumulator["expired_detected"] invece di scan.expired_count - risolve discrepanza tra "Scaduti rilevati" e "Appena Rilistati"

[2026-04-13T11:00:00Z] v1.4 Wait All Expired & Notifiche Dettagliate:
- Fuori dalle golden hours, il bot ora aspetta che TUTTI gli oggetti (inclusi quelli in 'processing') siano scaduti prima di effettuare il relist globale, mantenendo uniti gli stock listati.
- Aggiornato payload notifica batch Telegram: divisi i contatori mostrando "Attivi (con timer)", "Scaduti rilevati" e "Appena Rilistati".

[2026-04-12T23:30:00Z] v1.3 Golden Hour Bug Fixes shipped. 3 critical bugs fixed:
- Bug 1 (20da86e): Golden hour wait skips when already in :09-:11 window — was waiting 59 min from 16:10 to 17:10
- Bug 2 (aa52cb3): EA popup blocks Transfer List click — dismiss_popups() + Escape + 3-attempt retry
- Bug 3 (20da86e): Hold window too aggressive after last golden — override when get_next_golden_hour() is None
- Polling tweak (fe2c2ea): Ritardatari polling 15-20s random → 10s fixed
- 519 timeline simulation tests added. All 641 tests pass. Project in production/maintenance mode.

[2026-04-12T10:42:00Z] Batch Telegram notifications: bot accumulates relist events within 120s and sends single summary instead of multiple separate messages.

[2026-04-11T17:01:00Z] v1.2 Protection & Stealth shipped: Console Mode (/console, /online), Heartbeat (Clear Sold every 2.5-5 min), manual relist detection, EA Cannot Authenticate modal handling, /reboot command, batch notifications.

[2026-04-09T18:55:00Z] Reboot command fix: /reboot now works correctly using threading.Event in BotState + main loop check + subprocess respawn.

[2026-04-06T14:12:00Z] v1.1 Telegram Commands shipped: 8 Telegram commands, SoldHandler, BotState with thread safety. 112 tests pass.

[2026-04-06T00:00:00Z] Phase 6 planning complete: TELEGRAM-01 through TELEGRAM-10 all mapped.

[2026-03-27T17:25:00Z] Phase 5 complete. v1.0 MVP ready. Pre-navigazione, polling progressivo, secondi nei log.

[2026-03-26T18:25:00Z] Bug fix: Sold items detection — detector.py now recognizes Sold Items section.

[2026-03-26T18:15:00Z] Polling implementation: listing scade prima di sync_minute - 60s → loop ogni 15s, max 60s.

[2026-03-23T07:39:00Z] v1.0 Auto-Relist MVP shipped. Phases 1-5 complete. 68 tests pass.

[2026-03-23T00:58:00Z] Phase 3 planned. Phases 2-5 ready for execution.

[2026-03-23T00:46:00Z] Phase 2 complete. 21 tests pass. Navigator, detector, integration wired.

[2026-03-22T23:43:00Z] Phase 1 bug fixed: load_session() now uses context.add_cookies(). Phase 1 verified 4/4.

[2026-03-22T23:00:00Z] Project started: FIFA 26 Auto-Relist Bot.
