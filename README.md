# AI Personal Tech Support

AI Personal Tech Support is an individual IST 440W capstone for ordinary Windows PC users. It provides a local help desk interface with beginner-friendly AI replies and an optional scripted preview.

You can describe any Windows PC problem or choose one of five quick starts for Internet & Wi-Fi, Slow PC, Storage, Audio & Drivers, or Overheating & Gaming. Live replies can cite official support pages and guide you through one manual step at a time. The sidebar shows the current category, diagnostic stage, and notes. **New troubleshooting session** clears the chat, category, notes, sources, and troubleshooting steps.

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

- **Live AI.** The app starts in live mode when a key is configured. The app searches the bundled knowledge base locally. Sending a chat message or step feedback shares up to 11 recent live-mode messages, retained diagnostic notes and step outcomes, any manual category selection, and matching reference summaries with OpenAI. Leave out passwords and other sensitive information. One request returns the reply, diagnostic update, any cited IDs, and any guided step, capped at 1,000 output tokens with no automatic retries.
- **Simulated preview.** Turn on **Simulated preview** in the sidebar to use local keyword matching and scripted replies. Preview is the default when the key is missing. It bypasses knowledge retrieval and OpenAI. Preview messages and notes stay local, including when you switch back to live mode.

### Follow a diagnostic session

A clearly described problem outside the five specialized categories uses **General Troubleshooting**, even when no knowledge base entry applies. When the description is vague or several symptoms compete for attention, the assistant asks which problem to tackle and can leave the category unselected. The automatic category can change on any reply as the user supplies evidence. Click a quick start or **Use General Troubleshooting** to set a manual override. It stays selected until you change it or click **Use automatic category**. The sidebar shows a different automatic category when the assistant detects one while an override is active.

The five stages are **Problem identification**, **Gathering diagnostic information**, **Evaluating possible causes**, **Guided troubleshooting**, and **Resolution or escalation**. The stage reflects what the assistant is doing in its current reply, so it may skip ahead to a safe observation or return to diagnostic questions when new details come in.

Open **Diagnostic notes** to review the original description, reported details, possible causes, and open questions. Live notes retain user-reported details after those messages leave the recent-chat window. The app checks quoted facts against the user's messages before saving them. Possible causes remain hypotheses, and unknown details are left blank. A malformed reply leaves the last valid notes and stage in place.

### Try and report a troubleshooting step

A guided step shows a title, manual instructions, what to look for, and any safety warnings or prerequisites. Try the step only if it fits your situation. Use **Problem solved**, **Still having the problem**, or **Unable to complete this step** to report the outcome. You can type an optional description with any outcome. The app records your choice before requesting a follow-up, even if the request fails. An incomplete step stays unverified, and a confirmed result of **Problem solved** ends active guidance for that turn. Only the current step has feedback controls, while earlier steps and reported outcomes remain visible in the conversation.

The app leaves all actions to you. It performs no local diagnostics or automatic repairs. When appropriate, the assistant starts with an observation or a reversible action and explains risks before more disruptive steps. The conversation can be reset locally at any time.

## Local knowledge base

[data/knowledge_base.json](data/knowledge_base.json) contains 25 original troubleshooting summaries, five for each specialized category. Each entry has a stable ID, title, category, symptoms, possible causes, basic diagnostic steps, safety considerations, and the publisher, title, and URL of its source. The entries draw from 15 official pages by Microsoft Support, Dell Technologies, Intel, and AMD. The entry titles identify the focused summaries, and the source titles identify the publisher's articles.

[knowledge_base.py](knowledge_base.py) validates the file and builds an in-memory index on the first live search. It represents titles and symptoms as sparse TF-IDF vectors and ranks them by cosine similarity. The latest evidence drives retrieval. The original problem and retained symptoms help with short follow-ups, and findings that argue against an earlier explanation can suppress weak matches. Generic overlaps such as “update” and “install” alone are insufficient. A manual selection can give a relevant entry a small ranking preference. Previous automatic categories do not affect ranking. The retriever returns up to three entries and can return none for weak or competing matches.

Reference summaries are passed as data, separate from the assistant's instructions. The model can return IDs for entries it used. The app accepts only IDs from that turn's retrieval results and uses the bundled title, publisher, and URL to render numbered links beneath the reply. It keeps links with their original reply. **Retrieved references** in the sidebar lists entries supplied for the latest request. **Sources cited for this reply** lists entries the model cited and the app could validate. When no source is cited, the reply is labeled **General AI guidance**. ID validation verifies which material was available for the turn. It cannot independently verify that the source supports every recommendation.

On another Windows computer, follow the existing clone and dependency installation instructions above. The corpus ships with the project, and the index builds automatically. To validate and build it without an API key, run the following from the project root.

```powershell
.\.venv\Scripts\python.exe -m knowledge_base
```

The command should report `Indexed 25 troubleshooting entries.` Restart Streamlit after changing the bundled data. The local index requires no database service, model download, or paid embedding calls. If the data file is missing or invalid, the sidebar reports that the knowledge base is unavailable and live chat can continue with general guidance.

## Verify the app

Run the automated tests from the project root. Tests use mocked OpenAI responses and need no key.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Try these scenarios in the browser.

| Action | Expected outcome |
| --- | --- |
| Open the app. | The dark interface shows five quick starts and a chat input. The sidebar says **Ready to start**. |
| Turn on **Simulated preview**, select **Internet & Wi-Fi**, and send `My Wi-Fi disconnects during video calls.` | The sidebar shows the category and **In progress**. The user message and a **Simulated response · Placeholder** appear without using the API. |
| In live mode, send `My PC is acting up.` | A loading indicator appears while the app waits for OpenAI. The live reply asks what is happening, the category remains unselected, and the stage is **Problem identification**. |
| Follow up with `My Windows 11 laptop drops Wi-Fi during calls. My phone stays connected.` | The sidebar detects **Internet & Wi-Fi** and lists matching reference titles. **Diagnostic notes** can show Windows 11 and the reported symptoms. |
| Click **Storage**, then **Use automatic category**. | The sidebar shows the manual selection, then returns to the detected category. The conversation stays visible and the buttons make no API requests. |
| In a fresh live session, send `Windows Update fails with error 0x80070002 and will not install.` Follow with `I have 250 GB of free storage available and have restarted several times.` | The assistant should classify the issue as **General Troubleshooting** once the issue is clear. No low-storage references should be shown. The assistant should use the free-space and restart reports to choose a different line of inquiry. |
| In a fresh live session, send `My Bluetooth headphones say connected but I hear no sound. Give me one safe check and use a supplied reference if it supports the check.` | Look for one step and a numbered link displaying the original article title and publisher when the assistant cites the retrieved source. Any source link should stay with that reply after the next turn. |
| Try each of the three step feedback buttons in separate live sessions. Add a short observation with one of them. | The outcome and optional note appear in **Diagnostic notes**. **Problem solved** moves to **Resolution or escalation**. The other outcomes can produce a new step, question, or escalation. Each outcome sends one request and retires that step's controls. |
| Try sending a message made of only spaces. | The conversation stays unchanged. If the browser submits the message, the app asks for a description. |
| Click **New troubleshooting session**. | The conversation, category, notes, retrieval status, source links, and steps clear. The stage returns to **Problem identification** and the status to **Ready to start**. |

Try each of these in a fresh live session and look for the expected title under **Knowledge retrieval**.

| Category | Test message | Expected top title |
| --- | --- | --- |
| Internet & Wi-Fi | My Wi-Fi disconnects during video calls. | Wi-Fi drops during calls or streaming |
| Slow PC | The PC is slow at startup. | Windows takes a long time to start |
| Storage | My C: drive is almost full and Windows shows a low disk space warning. | Low free space on the system drive |
| Audio & Drivers | My Bluetooth headphones say connected but I hear no sound. | Bluetooth headset connects without sound |
| Overheating & Gaming | My laptop overheats and shuts down unexpectedly while gaming. | Laptop gets hot and shuts down during use |

For a no-match check, send `My PC is acting up.` in a fresh live session. The sidebar should say **No relevant entries found**, and the assistant can ask for more detail.

### Milestone 6 live AI validation

The project owner tested the live OpenAI integration using simulated user-reported troubleshooting scenarios. The review verified General Troubleshooting classification, improved retrieval relevance for Windows Update error `0x80070002`, appropriate clarification for ambiguous descriptions, and retention of reported diagnostic details. It also verified relevant source citations alongside AI replies, structured troubleshooting steps, all three step feedback options, and visible session reset behavior.

These results describe how the application responded to simulated reports and outcomes. They provide no evidence of an actual hardware repair.

## Current limitations

Live replies, categories, stage, citation choices, and steps depend on the model and the details you provide. TF-IDF depends on word overlap. It can miss unfamiliar wording or multiple issues in one report, and its handling of findings that contradict an earlier cause uses a few text patterns. A reported capacity can lower the relevance of storage references, but the app cannot confirm which drive it describes or whether Windows has enough space. The corpus covers the five specialized topics, so General Troubleshooting often has no matching references. The simulated preview demonstrates category and initial-stage behavior with keyword rules and scripted questions. It bypasses live step creation and retrieval. Messages are limited to 2,000 characters. Chat, notes, sources, and outcomes are kept in the active Streamlit session.

### Windows Update classification and retrieval

During Milestone 5 manual testing, reporting Windows Update error `0x80070002` led to a **Storage** classification and a storage-related reference. After the user reported **250 GB of free storage**, the assistant recognized that insufficient storage was unlikely. The category stayed **Storage**, and retrieval continued to return storage-related references.

The earlier implementation fed the previous automatic category into both the model's retained notes and the retriever's category preference. That preference could favor marginal storage matches from overlapping words such as “update,” “install,” or “free storage.” Milestone 6 keeps the previous category as a model hint and removes it from retrieval ranking. The original error and the recent free-space finding are covered by a regression test that uses local retrieval and mocked model replies.
