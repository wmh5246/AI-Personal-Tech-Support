# AI Personal Tech Support

AI Personal Tech Support is an individual IST 440W capstone for ordinary Windows PC users. It provides a local help desk interface with beginner-friendly AI replies and an optional scripted preview.

You can describe a problem directly or choose Internet & Wi-Fi, Slow PC, Storage, Audio & Drivers, or Overheating & Gaming. The sidebar shows the current category, diagnostic stage, and notes. **New troubleshooting session** clears the chat, notes, and category selection.

## Windows prerequisites

- A 64-bit Windows 10 or 11 computer, PowerShell, and a web browser.
- 64-bit Python 3.12 with the Windows `py` launcher. The app was tested on Windows 11 with Python 3.12.14. [Python downloads for Windows](https://www.python.org/downloads/windows/)
- Git for Windows to clone the repository. [Git for Windows](https://git-scm.com/install/windows)
- Internet access for setup and live AI replies. The installed simulated preview runs without an API key or API charges.

## Install from PowerShell

Clone the repository or open PowerShell in an existing checkout.

```powershell
git clone https://github.com/wmh5246/AI-Personal-Tech-Support.git
Set-Location AI-Personal-Tech-Support
```

From the project root, check Python, create the virtual environment, and install the pinned packages.

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

The version check should report Python 3.12.x, and the dependency check should report `No broken requirements found.` If PowerShell cannot find `py` or Python 3.12, install the Windows launcher and a 64-bit Python 3.12 runtime, then open a fresh PowerShell window. If the package installation fails because PyPI is unreachable, restore Internet access and rerun the install command.

The commands call the virtual environment's Python directly, so they work without running an activation script or changing PowerShell's execution policy.

## Configure live AI

1. Sign in to the OpenAI API platform, select your project, and create a secret API key. The key needs permission to use the Responses API and your chosen model. [OpenAI API key settings](https://platform.openai.com/api-keys)
2. Create a local `.env` file in the repository root if you do not already have one.

   ```powershell
   if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
   notepad .env
   ```

3. In the local file, paste your key after `OPENAI_API_KEY=` and save. Git ignores `.env`. Keep the tracked `.env.example` key field blank.
4. To use a different model, set `OPENAI_MODEL` in `.env` to a model your project can access that supports the Responses API and Structured Outputs. The default is `gpt-5.4-mini`. A PowerShell setting such as `$env:OPENAI_MODEL = 'gpt-5.4-mini'` takes precedence over the file for that terminal session. [GPT-5.4 mini model reference](https://developers.openai.com/api/docs/models/gpt-5.4-mini)

OpenAI API usage is billed separately from ChatGPT subscriptions. Live replies use input and output tokens, including recent live conversation history sent with each message. Check your API project billing and current model prices before using live mode. [API pricing](https://developers.openai.com/api/docs/pricing) · [OpenAI billing help](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform)

## Launch

Run this from the project root, then open the local URL printed in PowerShell. The usual address is [127.0.0.1:8501](http://127.0.0.1:8501).

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Keep PowerShell open while using the app. Press **Ctrl+C** in that window to stop it. To choose a specific available port, append an option such as `--server.port 8502` to the launch command.

### Choose a reply mode

- **Live AI.** The app starts in live mode when a key is configured. Sending a message shares up to 11 recent live-mode messages, the retained live diagnostic notes, and any manual category selection with OpenAI. Leave out passwords and other sensitive information. One request returns both the chat reply and a structured update, capped at 800 output tokens total, with no automatic retries.
- **Simulated preview.** Turn on **Simulated preview** in the sidebar to use local keyword matching and scripted replies. Preview is the default when the key is missing. Preview messages and notes stay local, including when you switch back to live mode.

### Follow a diagnostic session

The assistant asks for clarification when the symptom could fit several categories. To correct the category, click a quick start. To return to the assistant's detected category, click **Use automatic category** in the sidebar.

The five stages are **Problem identification**, **Gathering diagnostic information**, **Evaluating possible causes**, **Guided troubleshooting**, and **Resolution or escalation**. The stage reflects what the assistant is doing in its current reply, so it may skip ahead to a safe observation or return to diagnostic questions when new details come in.

Open **Diagnostic notes** to review the original description, reported details, possible causes, and open questions. Live notes retain user-reported details after those messages leave the recent-chat window. The app checks quoted facts against the user's messages before saving them. Possible causes remain hypotheses, and unknown details are left blank. A malformed reply leaves the last valid notes and stage in place.

## Verify the app

Run the automated tests from the project root.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Try these scenarios in the browser.

| Action | Expected outcome |
| --- | --- |
| Open the app. | The dark interface shows five quick starts and a chat input. The sidebar says **Ready to start**. |
| Turn on **Simulated preview**, select **Internet & Wi-Fi**, and send `My Wi-Fi disconnects during video calls.` | The sidebar shows the category and **In progress**. The user message and a **Simulated response · Placeholder** appear without using the API. |
| In live mode, send `My PC is acting up.` | A loading indicator appears while the app waits for OpenAI. The live reply asks what is happening, the category remains unselected, and the stage is **Problem identification**. |
| Follow up with `My Windows 11 laptop drops Wi-Fi during calls. My phone stays connected.` | The sidebar detects **Internet & Wi-Fi**. The app can ask a targeted question, compare causes, or suggest a safe observation. **Diagnostic notes** can show Windows 11 and the reported symptoms. |
| Click **Storage**, then **Use automatic category**. | The sidebar shows the manual selection, then returns to the detected category. The conversation stays visible and the buttons make no API requests. |
| Try sending a message made of only spaces. | The conversation stays unchanged. If the browser submits the message, the app asks for a description. |
| Click **New troubleshooting session**. | The conversation, category, and notes clear. The stage returns to **Problem identification** and the status to **Ready to start**. |

## Current limitations

Live replies, classification, and the choice of stage depend on the model and the details you provide. The app checks that note excerpts occur in your messages. It cannot independently verify the state of the PC. The simulated preview demonstrates category and initial-stage behavior with simple keyword rules and scripted questions. It does not extract detailed notes or advance through the full live workflow. Messages are limited to 2,000 characters. Chat and notes are kept only in the active Streamlit session and clear when you reload the page or start a new session.
