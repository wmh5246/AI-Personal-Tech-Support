# AI Personal Tech Support

AI Personal Tech Support is an individual IST 440W capstone for ordinary Windows PC users. It provides a local help desk interface with beginner-friendly AI replies and an optional scripted preview.

You can describe a problem directly or choose Internet & Wi-Fi, Slow PC, Storage, Audio & Drivers, or Overheating & Gaming. The sidebar shows your selected category and session status. The chat keeps the current conversation in memory, and **New troubleshooting session** clears the messages and category.

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
4. To use a different model, set `OPENAI_MODEL` in `.env` to a Responses API model your project can access. The default is `gpt-5.4-mini`. A PowerShell setting such as `$env:OPENAI_MODEL = 'gpt-5.4-mini'` takes precedence over the file for that terminal session. [GPT-5.4 mini model reference](https://developers.openai.com/api/docs/models/gpt-5.4-mini)

OpenAI API usage is billed separately from ChatGPT subscriptions. Live replies use input and output tokens, including recent live conversation history sent with each message. Check your API project billing and current model prices before using live mode. [API pricing](https://developers.openai.com/api/docs/pricing) · [OpenAI billing help](https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform)

## Launch

Run this from the project root, then open the local URL printed in PowerShell. The usual address is [127.0.0.1:8501](http://127.0.0.1:8501).

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Keep PowerShell open while using the app. Press **Ctrl+C** in that window to stop it. To choose a specific available port, append an option such as `--server.port 8502` to the launch command.

### Choose a reply mode

- **Live AI.** The app starts in live mode when a key is configured. Sending a message shares the last 11 live-mode messages, including the new message, and the selected category with OpenAI. Leave out passwords and other sensitive information. The app makes one request per submission, caps output at 400 tokens, and uses no automatic retries.
- **Simulated preview.** Turn on **Simulated preview** in the sidebar to use the local scripted replies. Preview is the default when the key is missing. Preview messages stay local, including when you switch back to live mode.

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
| With a key configured, turn off **Simulated preview** and send the same example. | A loading indicator appears while the app waits for OpenAI. The response is labeled **Live AI · OpenAI**. |
| In live mode, follow up with `It also affects my phone.` | The assistant has the earlier Wi-Fi description for context. Both turns remain visible. Changing category updates the sidebar without sending a request. |
| Try sending a message made of only spaces. | The conversation stays unchanged. If the browser submits the message, the app asks for a description. |
| Click **New troubleshooting session**. | The category and conversation clear, the status returns to **Ready to start**, and you can send a new message. |

## Current limitations

Live replies are AI-generated suggestions based on what you describe. The app has no access to your computer's diagnostics and does not retrieve or verify sources. Messages are limited to 2,000 characters. Conversation history is kept only in the active Streamlit session and disappears when you reload the page or start a new session.
