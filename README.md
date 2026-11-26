# AI Personal Tech Support

AI Personal Tech Support is an individual IST 440W capstone for ordinary Windows PC users. The project aims to recreate a structured help desk conversation. Future milestones will add AI-guided troubleshooting, trusted technical sources, and consent-based diagnostics.

Milestone 1 is a local interface preview. You can describe a problem directly or choose Internet & Wi-Fi, Slow PC, Storage, Audio & Drivers, or Overheating & Gaming. The sidebar shows your selected category and session status. The chat keeps the current conversation in memory, and **New troubleshooting session** clears the messages and category.

## Windows prerequisites

- A 64-bit Windows 10 or 11 computer, PowerShell, and a web browser.
- 64-bit Python 3.12 with the Windows `py` launcher. Milestone 1 was tested on Windows 11 with Python 3.12.14. [Python downloads for Windows](https://www.python.org/downloads/windows/)
- Git for Windows to clone the repository. [Git for Windows](https://git-scm.com/install/windows)
- Internet access to download the project and Python packages during setup. Running the installed preview requires no OpenAI account, API key, or API spending.

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

## Launch

Run this from the project root, then open [127.0.0.1:8501](http://127.0.0.1:8501) in your browser.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Keep PowerShell open while using the app. Press **Ctrl+C** in that window to stop it. If port 8501 is already in use, append `--server.port 8502` to the launch command and open [127.0.0.1:8502](http://127.0.0.1:8502).

## Verify Milestone 1

Run the automated tests from the project root.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Try these scenarios in the browser.

| Action | Expected outcome |
| --- | --- |
| Open the app. | The dark interface shows five quick starts and a chat input. The sidebar says **Ready to start**. |
| Select **Internet & Wi-Fi** and send `My Wi-Fi disconnects during video calls.` | The sidebar shows the category and **In progress**. The user message and a **Simulated response · Placeholder** appear. |
| Send `It also affects my phone.` | Both turns remain visible. Changing category updates the sidebar while preserving the conversation. |
| Try sending a message made of only spaces. | The conversation stays unchanged. If the browser submits the message, the app asks for a description. |
| Click **New troubleshooting session**. | The category and conversation clear, the status returns to **Ready to start**, and you can send a new message. |

## Current limitations

Replies are scripted placeholders. This preview covers problem intake and chat history. The OpenAI API, documentation retrieval, diagnostics, guided steps, and session reports are planned for later milestones. Messages are limited to 2,000 characters. Conversation history is kept only in the active Streamlit session and disappears when you reload the page or start a new session.

`.env.example` reserves a setting for future OpenAI integration. This milestone neither requires nor reads a `.env` file. Later API usage may incur charges, which will be documented when the integration is added.
