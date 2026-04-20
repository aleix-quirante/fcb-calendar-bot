# Barça Calendar Bot - Project Plan

## Overview
The Barça Calendar Bot synchronizes FC Barcelona's upcoming matches from an ICS feed to Google Calendar, enriching events with win probabilities from ClubElo and pre-match analysis generated via an LLM.

## Core Features
- **Calendar Sync**: Fetches matches from `https://ics.fixtur.es/v2/fc-barcelona.ics` and syncs to Google Calendar.
- **Win Probability Integration**: Uses ClubElo API to calculate and display win chances for each match.
- **Pre-Match Analysis**: Generates detailed match analysis using LLM (Ollama/LocalAI) when enabled.
- **Event Cleanup**: Automatically removes outdated events using `CalendarCleaner`.

## Architecture
- **Main Workflow**: `bot_barca.py` orchestrates:
  1. Fetching ICS events
  2. Calculating win probabilities
  3. Syncing to Google Calendar
  4. Generating pre-match analysis (if enabled)
- **Configuration**: Centralized via `src/shared/config.py` using Pydantic settings.
- **Sports Summary Agent**: Located in `src/sports_summary_agent/`, handles analysis generation using:
  - `feed_client.py` (fetches news)
  - `llm_client.py` (generates analysis)
  - `agent.py` (orchestrates workflow)

## Key Configuration
| Setting | Default | Description |
|---------|---------|-------------|
| `BARCA_ICS_URL` | `https://ics.fixtur.es/v2/fc-barcelona.ics` | ICS feed source |
| `BARCA_GOOGLE_CALENDAR_ID` | `primary` | Google Calendar ID |
| `BARCA_SUMMARY_ENABLED` | `True` | Toggle for pre-match analysis |
| `BARCA_OLLM_BASE_URL` | `http://localhost:11434/v1` | LLM API endpoint |
| `BARCA_RETENTION_DAYS` | `7` | Days to retain past events |

## Future Enhancements
1. Support for multiple teams (not just Barcelona)
2. Post-match analysis using RSS feed (`BARCA_RSS_FEED_URL`)
3. Improved error handling for ClubElo API failures
4. User-configurable analysis templates via LLM prompts
5. Integration with ClubElo's official API (when available)

## Dependencies
- `google-api-python-client` (Google Calendar API)
- `icalendar` (ICS parsing)
- `requests` (API calls)
- `pydantic-settings` (configuration)
- `Ollama/LocalAI` (LLM for analysis)