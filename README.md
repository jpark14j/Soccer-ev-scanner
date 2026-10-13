# Daily Telegram digest for your EXISTING Soccer EV Scanner

This replaces the **previous 30-minute alerts package**. **Do not install both schedules.**

Every morning at approximately **9:00 a.m. Toronto time**, the background GitHub Action scans four leagues and sends **one Telegram message** summarizing up to three qualifying picks (singles or parlays). If none qualify, it sends **"No strong picks today."** It does not place bets. GitHub scheduling can be delayed; delivery time is not guaranteed.

## Install on your iPhone

1. Extract the ZIP.
2. In your **existing** `Soccer-ev-scanner` GitHub repository, upload `scanner_core.py` and `telegram_alerts.py` beside `app.py`.
3. Add the workflow at `.github/workflows/telegram_alerts.yml` (GitHub **Add file → Create new file** lets you type the full path). If you already installed the previous 30-minute version, **replace** the old `telegram_alerts.py` and `.github/workflows/telegram_alerts.yml` rather than adding a second workflow.
4. Keep your existing GitHub Actions secrets `ODDS_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `TELEGRAM_CHAT_ID` unchanged.
5. In GitHub **Settings → Actions → General**, enable workflow **Read and write permissions** so the workflow can record the date of its last sent message. On restricted repositories, the workflow may fail to persist this state.
6. GitHub **Actions → Soccer Picks Daily Telegram Digest** will show scheduled runs. You can test via **Run workflow** during Toronto morning hours (09:00–11:59). Outside that window the script exits without sending.

## Notes

- The workflow is scheduled twice in UTC solely to accommodate Toronto daylight-saving changes; **the script sends at most one message per Toronto calendar day**, provided its state commit succeeds. GitHub scheduling may be delayed or skipped.
- Up to **two scans per day** may occur if the first run fails to send or state is not saved. A successful morning digest generally costs **four Odds API sport requests per day** (about 120 per 30-day month), but actual API quota charges depend on your plan and endpoint.
- The statistical model is experimental and not backtested. Recommendations are research prompts, not evidence of guaranteed profits.
- Your Streamlit app and its `app.py` remain unchanged.
