# JARVIS Performance Features - Anleitung

Diese Anleitung erklärt alle Performance-Optimierungs-Features von JARVIS und wie man sie konfiguriert und nutzt.

## Übersicht

JARVIS verfügt über drei Phasen von Performance-Optimierungen, die über die `config.yaml` Datei aktiviert werden können. Alle Features sind unter `performance.flags` zu finden.

## Phase 1: Quick Wins

Diese Features bieten sofortige Performance-Verbesserungen mit minimalem Risiko.

### cache_system_prompt
**Standard:** `true`

Cacht das System-Prompt mit einer 5-minütigen TTL (Time-To-Live).

- **Vorteil:** Reduziert wiederholte API-Calls für das System-Prompt
- **Wann aktivieren:** Immer empfohlen
- **Wann deaktivieren:** Wenn du häufig System-Prompt-Änderungen testest

### lazy_tool_declarations
**Standard:** `true`

Lädt Tool-Deklarationen lazy (bei Bedarf) statt beim Start.

- **Vorteil:** Schnellerer Start, weniger Speicher beim Initialisieren
- **Wann aktivieren:** Immer empfohlen
- **Wann deaktivieren:** Wenn du Tool-Declarations sofort beim Start brauchst

### optimized_audio_chunks
**Standard:** `true`

Verwendet 4096-Byte Audio-Chunks mit Double Buffering für bessere Audio-Performance.

- **Vorteil:** Reduziert Audio-Latenz und Verzögerungen
- **Wann aktivieren:** Für Voice-Interaktion immer empfohlen
- **Wann deaktivieren:** Bei Audio-Problemen oder Kompatibilitätsproblemen

### cache_api_responses
**Standard:** `true`

Cacht API-Antworten mit einer 10-minütigen TTL.

- **Vorteil:** Reduziert redundante API-Calls für gleiche Anfragen
- **Wann aktivieren:** Immer empfohlen
- **Wann deaktivieren:** Wenn du immer frische API-Antworten benötigst

### preload_embedding_model
**Standard:** `true`

Lädt das Embedding-Modell beim Start vor.

- **Vorteil:** Erste semantische Suche ist schneller
- **Wann aktivieren:** Wenn du semantische Suche regelmäßig nutzt
- **Wann deaktivieren:** Um Speicher beim Start zu sparen

### debounce_ui_updates
**Standard:** `true`

Debounced UI-Updates auf 1-Sekunden-Intervalle.

- **Vorteil:** Reduziert UI-Flackern und CPU-Auslastung
- **Wann aktivieren:** Für UI-Nutzung immer empfohlen
- **Wann deaktivieren:** Wenn du sofortige UI-Updates benötigst

### async_logging
**Standard:** `true`

Verwendet asynchrones Logging mit Queue.

- **Vorteil:** Logging blockiert nicht die Hauptausführung
- **Wann aktivieren:** Immer empfohlen
- **Wann deaktivieren:** Bei Logging-Problemen oder Debugging

## Phase 2: Medium-Impact

Diese Features bieten mittlere Performance-Verbesserungen mit geringem Risiko.

### lazy_load_actions
**Standard:** `true`

Lädt Action-Module lazy (bei Bedarf) statt beim Import.

- **Vorteil:** Schnellerer Start, weniger Speicher
- **Wann aktivieren:** Immer empfohlen
- **Wann deaktivieren:** Wenn du alle Actions sofort beim Start brauchst

### connection_pooling
**Standard:** `true`

Verwendet Connection Pooling für externe APIs (HTTP).

- **Vorteil:** Reduziert Verbindungsaufbau-Overhead
- **Wann aktivieren:** Für externe API-Calls immer empfohlen
- **Wann deaktivieren:** Bei Verbindungsproblemen

### aggressive_compression
**Standard:** `true`

Aggressive Kompression für alte Nachrichten und Daten.

- **Vorteil:** Reduziert Speicherverbrauch für alte Daten
- **Wann aktivieren:** Bei Speicherproblemen
- **Wann deaktivieren:** Wenn CPU-Performance wichtiger ist als Speicher

### db_connection_pooling
**Standard:** `true`

Verwendet Connection Pooling für Datenbanken (SQLite).

- **Vorteil:** Bessere DB-Performance, weniger Verbindungsaufbau
- **Wann aktivieren:** Immer empfohlen
- **Wann deaktivieren:** Bei DB-Kompatibilitätsproblemen

### vector_db_cache
**Standard:** `true`

Cacht Vector-DB-Abfragen mit 1-Stunden-TTL.

- **Vorteil:** Schnellere wiederholte semantische Suchen
- **Wann aktivieren:** Wenn du semantische Suche nutzt
- **Wann deaktivieren:** Wenn du immer frische Suchergebnisse brauchst

### batch_screen_processing
**Standard:** `true`

Batch-Verarbeitung für Screen-Captures mit Queue-System.

- **Vorteil:** Bessere Performance bei mehreren Screens
- **Wann aktivieren:** Für Passive Vision immer empfohlen
- **Wann deaktivieren:** Bei Screen-Processing-Problemen

### event_file_watching
**Standard:** `true`

Verwendet event-basiertes File Watching (watchdog) statt Polling.

- **Vorteil:** Sofortige Reaktion auf Dateiänderungen, weniger CPU
- **Wann aktivieren:** Für File Watching immer empfohlen
- **Wann deaktivieren:** Wenn watchdog nicht verfügbar ist

## Phase 3: Complex Changes

Diese Features bieten große Performance-Verbesserungen, erfordern aber mehr Testing.

### reduce_memory_footprint
**Standard:** `true`

Implementiert State Sharding und Garbage Collection für reduzierten Speicherverbrauch.

- **Vorteil:** Deutlich weniger Speicherverbrauch
- **Wann aktivieren:** Bei Speicherproblemen
- **Wann deaktivieren:** Bei Stabilitätsproblemen

### parallel_tool_execution
**Standard:** `true`

Führt unabhängige Tools parallel aus.

- **Vorteil:** Schnellere Ausführung bei multiplen Tools
- **Wann aktivieren:** Wenn du oft mehrere Tools gleichzeitig nutzt
- **Wann deaktivieren:** Bei Race Conditions oder Stabilitätsproblemen

### async_workflow_engine
**Standard:** `true`

Verwendet asynchrone Task Queue für Workflows.

- **Vorteil:** Bessere Workflow-Performance und Skalierbarkeit
- **Wann aktivieren:** Für Workflow-Nutzung immer empfohlen
- **Wann deaktivieren:** Bei Workflow-Problemen

### precompute_queries
**Standard:** `true`

Berechnet häufige Anfragen im Voraus.

- **Vorteil:** Sofortige Antworten für häufige Queries
- **Wann aktivieren:** Wenn du oft gleiche Fragen stellst
- **Wann deaktivieren:** Um Speicher zu sparen

### response_streaming
**Standard:** `true`

Streamt API-Antworten statt zu warten auf vollständige Antwort.

- **Vorteil:** Schnellere sichtbare Antworten
- **Wann aktivieren:** Für bessere User Experience immer empfohlen
- **Wann deaktivieren:** Bei Streaming-Problemen

### async_ui_server
**Standard:** `true`

Verwendet aiohttp für UI Server statt synchronem Server.

- **Vorteil:** Bessere UI-Performance und Konkurrenzfähigkeit
- **Wann aktivieren:** Für UI-Nutzung immer empfohlen
- **Wann deaktivieren:** Bei UI-Server-Problemen

## Konfiguration

Alle Features werden in der `config.yaml` Datei unter `performance.flags` konfiguriert:

```yaml
performance:
  enabled: true
  flags:
    # Phase 1: Quick Wins
    cache_system_prompt: true
    lazy_tool_declarations: true
    optimized_audio_chunks: true
    cache_api_responses: true
    preload_embedding_model: true
    debounce_ui_updates: true
    async_logging: true
    
    # Phase 2: Medium-Impact
    lazy_load_actions: true
    connection_pooling: true
    aggressive_compression: true
    db_connection_pooling: true
    vector_db_cache: true
    batch_screen_processing: true
    event_file_watching: true
    
    # Phase 3: Complex Changes
    reduce_memory_footprint: true
    parallel_tool_execution: true
    async_workflow_engine: true
    precompute_queries: true
    response_streaming: true
    async_ui_server: true
```

## Empfehlungen

### Für maximale Performance
Aktiviere alle Features auf `true`. Dies bietet die beste Performance für die meisten Anwendungsfälle.

### Für maximale Stabilität
Deaktiviere Phase 3 Features und behalte nur Phase 1 und 2 aktiv.

### Für minimale Speichernutzung
Aktiviere `aggressive_compression`, `reduce_memory_footprint`, und deaktiviere `preload_embedding_model`.

### Für Debugging
Deaktiviere `async_logging` und `cache_api_responses` für bessere Debugging-Möglichkeiten.

## Performance-Monitoring

JARVIS verfügt über integriertes Performance-Monitoring. Du kannst die Performance-Statistiken über die Logs oder das Performance-Dashboard abrufen.

### Wichtige Metriken
- **Cache Hit Rate:** Wie oft Caches erfolgreich genutzt wurden
- **API Latency:** Durchschnittliche API-Antwortzeit
- **Memory Usage:** Aktueller Speicherverbrauch
- **CPU Usage:** Aktuelle CPU-Auslastung

## Troubleshooting

### Probleme nach Aktivierung
1. Deaktiviere Phase 3 Features zuerst
2. Wenn das Problem persists, deaktiviere Phase 2 Features
3. Als letzten Ausweg deaktiviere Phase 1 Features einzeln

### Speicherprobleme
- Deaktiviere `preload_embedding_model`
- Aktiviere `aggressive_compression`
- Aktiviere `reduce_memory_footprint`

### Langsame Performance
- Überprüfe, ob alle Features aktiviert sind
- Prüfe die Performance-Logs für Engpässe
- Erwäge Hardware-Upgrades

## Zusätzliche Ressourcen

- `config.yaml` - Hauptkonfigurationsdatei
- `core/performance_monitor.py` - Performance-Überwachung
- `core/cache_manager.py` - Cache-Management
- `core/connection_pool.py` - Connection Pooling

## Support

Bei Problemen mit Performance-Features:
1. Prüfe die Logs unter `logs/`
2. Deaktiviere problematische Features
3. Melde Issues mit detaillierten Logs
