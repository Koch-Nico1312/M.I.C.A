# M.I.C.A Kommunikationszentrale

M.I.C.A bündelt Telegram, Discord, Companion-Geräte, proaktive Hinweise,
Telefonie und Home Assistant in einer gemeinsamen Kommunikationsschicht. Die
Oberfläche ist über das Verbindungs-Symbol in der oberen Leiste erreichbar.

## Sicherheitsmodell

- Eingehende Absender müssen über eine Chat-ID, Telefonnummer oder ein
  bestätigtes Companion-Pairing freigegeben sein.
- Nachrichten nach außen, neue Pairings, Smart-Home-Aktionen und jeder einzelne
  Telefonanruf benötigen eine ausdrückliche Bestätigung.
- Telefonziele müssen zusätzlich in `allowed_numbers` stehen.
- Zugangsdaten werden nur in der lokalen Konfiguration gespeichert und niemals
  über den Status-Endpunkt ausgegeben.
- Twilio-Webhooks werden standardmäßig über `X-Twilio-Signature` geprüft.
- Der Kommunikationsverlauf speichert keine Tokens.

## Telegram

1. Über BotFather einen Bot erstellen und den Bot-Token kopieren.
2. Dem Bot eine Nachricht senden und die eigene Chat-ID ermitteln.
3. In M.I.C.A die Kommunikationszentrale öffnen, Token und Chat-ID eintragen
   und **Sicher verbinden** wählen.

Danach empfängt M.I.C.A Nachrichten automatisch per Long Polling. Unterstützt
werden freier Text, `/status`, `/approvals`, `/approve TOOL ACTION`,
`/deny TOOL ACTION`, Inline-Freigaben und Sprachnachrichten. Sprachdateien
werden unter `data/communications/telegram` lokal abgelegt und als Anhang an
den aktiven M.I.C.A-Dialog übergeben.

Alternativ können `TELEGRAM_ENABLED`, `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_CHAT_ID` und `TELEGRAM_ALLOWED_SENDER_IDS` verwendet werden.

## Telefonie

Unterstützt werden Twilio und ein eigener SIP-HTTP-Bridge. Für Twilio werden
Account SID, Auth Token, eine Absendernummer, erlaubte Zielnummern und optional
eine öffentliche HTTPS-Webhook-URL benötigt. Ausgehende Anrufe können eine
Nachricht sprechen. Eingehende Sprache wird über den Provider transkribiert
und als gepaarte Telefon-Nachricht an M.I.C.A weitergeleitet.

Der lokale Endpunkt lautet `POST /api/communications/telephony`. Wird eine
öffentliche URL verwendet, muss sie auf diesen lokalen Endpunkt zeigen. Die
Aufzeichnung oder Transkription von Gesprächen darf nur entsprechend den
geltenden Einwilligungs- und Datenschutzregeln verwendet werden.

## Companion und Mobilgerät

Ein über `/api/companion/pair` erzeugter Code aktiviert eine zeitlich begrenzte
Companion-Sitzung. Die Browser-Erweiterung unter `extensions/browser-companion`
verwendet anschließend dieselbe Kommunikationsschicht, kann Aufgaben an
M.I.C.A senden und den eingeschränkten Arbeitsbereich abrufen. Beim Widerruf
der Companion-Sitzung wird auch die Kommunikationsidentität entfernt.

## Proaktive Hinweise

Nach der Telegram-Einrichtung kann die bestehende Supervisor-Automation
priorisierte Hinweise zusätzlich an Telegram zustellen. Ruhezeiten,
Prioritätsschwelle, Fokusmodus und Deduplizierung bleiben zentral erhalten.
Telefonanrufe werden dabei nicht automatisch ausgelöst; dafür ist weiterhin
eine Bestätigung pro Anruf erforderlich.

## Home Assistant

Die Kommunikationszentrale nimmt Home-Assistant-URL und Long-Lived Access
Token entgegen und verwendet `core/smart_home.py` für Geräteabgleich und
Aktionen. Geräteschaltungen sind bestätigungspflichtig. Tokens bleiben in
`config/smart_home.json` und erscheinen nicht in API-Antworten.

## Lokale API

- `GET /api/communications` – redigierter Status, Pairings und Verlauf
- `POST /api/communications` – Aktionen `configure`, `pair`, `revoke`, `send`,
  `poll`, `telegram_update`, `inbound`, `call`, `notify`, `home_configure` und
  `home_action`
- `POST /api/communications/telephony` – signierter Telefonie-Webhook

Alle externen Integrationen bleiben ohne Zugangsdaten deaktiviert. Dadurch
startet M.I.C.A weiterhin vollständig lokal und ohne neue Pflichtdienste.
