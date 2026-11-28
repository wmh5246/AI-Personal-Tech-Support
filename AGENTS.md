# AI Personal Tech Support development guide

## Project purpose and scope

AI Personal Tech Support is an individual IST 440W university capstone. Build a locally hosted, browser-based troubleshooting assistant for ordinary Windows PC users. Running on the user's PC lets the application collect basic diagnostic information from that computer with consent.

Reproduce a structured help desk experience through conversational diagnostic questions, retrieval of trusted documentation from multiple vendors, AI selection of safe diagnostic tools, visible findings and sources, step-by-step guidance with user feedback, and a resolution or escalation summary.

Use these capabilities to distinguish the prototype from general-purpose chatbots, Windows Agent in Settings, manufacturer-specific support apps, and enterprise IT support platforms. Keep the scope feasible for one student in one semester. Avoid claims of being the first AI troubleshooting agent or outperforming commercial enterprise products.

Prioritize application stability, simplicity, maintainability, and reproducibility when making scope and implementation decisions. Account registration, authentication, cloud synchronization, automatic system repairs, and standalone desktop packaging are outside the current project scope.

## Technology choices

- Retain the existing Python and Streamlit architecture for the local browser application.
- Use the OpenAI API for language model capabilities and tool calling.
- Retain the local TF-IDF retrieval implementation for retrieval-augmented generation (RAG). Introduce ChromaDB or embedding models only when a demonstrated requirement justifies the change.
- Prefer Python's standard library and lightweight packages for local diagnostics.
- Use Git and GitHub for version control and Pytest or a suitable lightweight testing tool.
- Target local execution on Windows. Favor simple, reliable implementations and avoid major architectural changes and unnecessary dependencies.

## Product requirements

Implement these capabilities incrementally in the milestone order below.

1. Accept natural-language descriptions of computer problems.
2. Provide quick starts for the five specialized troubleshooting categories and support General Troubleshooting for other Windows issues.
3. Ask relevant diagnostic follow-up questions in conversation.
4. Retain conversation context within the current session.
5. Retrieve relevant technical documentation through RAG.
6. Cite sources for technical recommendations.
7. Let the AI select among the available diagnostic tools.
8. Guide users one step at a time and collect feedback after each step.
9. Produce troubleshooting session summaries.
10. Recommend safe escalation when a problem remains unresolved.
11. Let users start and reset troubleshooting sessions.
12. Allow optional local chat history in SQLite, with controls to view, resume, and delete saved sessions.

### Specialized knowledge base categories

- Internet and Wi-Fi connectivity
- Slow PC performance
- Low storage and disk space
- Audio and driver issues
- Overheating and gaming performance

Support all five specialized categories and use General Troubleshooting for Windows issues outside them or when a specialized category is unclear. Allow automatically selected categories to change as new evidence becomes available. Get the project owner's approval for additional scope changes or unrelated features.

## Agent workflow and diagnostic tools

1. Receive the user's description of the problem.
2. Ask relevant diagnostic questions.
3. Determine whether more information is needed.
4. Select an appropriate diagnostic or retrieval tool when needed.
5. Execute the approved tool after obtaining consent if it collects local system information.
6. Interpret the returned information and distinguish observations from suspected causes.
7. Recommend a suitable troubleshooting step.
8. Use the user's feedback to decide the next step.
9. Conclude with a resolution summary or recommend escalation.

| Planned function | Purpose |
| --- | --- |
| `search_knowledge_base()` | Retrieve relevant technical support documentation. |
| `get_system_info()` | Collect basic operating system, processor, and memory information. |
| `check_disk_space()` | Retrieve actual available disk space. |
| `analyze_error_message()` | Identify or classify a user-provided error message. |

- Expose an explicit, restricted set of callable functions. Never give the model unrestricted access to PowerShell, terminals, or arbitrary system commands.
- Report diagnostic results only from actual tool execution. Show which tools ran and their relevant findings in the interface.
- Bound tool-calling loops to prevent repeated actions and uncontrolled API usage.
- Consider additional read-only tools after the planned capabilities work reliably.

## Knowledge base and citations

- Build a small, curated knowledge base from reliable technical documentation. Use relevant guidance from Microsoft Support, Dell, Intel, NVIDIA or AMD, and other hardware manufacturers as appropriate.
- Respect source usage permissions. Store original summaries, permitted excerpts where appropriate, and source metadata. Include the title, source URL, troubleshooting category, and relevant content for each entry.
- Retrieve relevant documentation before generating technical recommendations. Display citations only for sources actually retrieved for the recommendation.
- Communicate uncertainty when retrieval finds no relevant documentation. Never invent sources.
- Reassess retrieval relevance when new evidence rules out a suspected cause. Use the Windows Update case documented in the README to investigate category anchoring and keyword overlap during Milestone 6.
- Include the knowledge base resources or the steps needed to rebuild it on another computer.

## Interface

Use a clean, professional dark theme inspired by the paper demo, with a dark navy background and blue or cyan accents. Use language ordinary Windows users can understand. Prioritize usability and functional reliability when adapting the demo.

- Show the application title, a brief introduction, and a natural-language problem input.
- Provide quick starts for all five specialized categories and offer General Troubleshooting.
- Display the chat conversation and current troubleshooting status.
- Make diagnostic tool usage, relevant results, guided steps, and supporting sources easy to find.
- Show the resolution or escalation summary and provide controls to start or reset a session.

## Safety, privacy, and user control

- Obtain user consent before collecting local system information. Explain beforehand what diagnostic information may be sent to the external OpenAI API.
- Keep diagnostic tools read-only and avoid collecting unnecessary personal or sensitive information.
- Never automatically change Windows settings or install or uninstall drivers or applications. Never delete user files or modify the Windows registry, BIOS, or disk partitions.
- Keep API credentials outside source code and never commit keys or other secrets to GitHub.
- Let users choose whether to save chat history locally. Limit the history deletion control to saved records managed by the application, and exclude local database files from Git.
- Clearly distinguish observed facts from suspected causes. Prefer low-risk recommendations and suggest professional technical support when appropriate.
- Leave actions that modify the computer under the user's control.

## Reproducibility on Windows

Treat reproducibility as a mandatory academic requirement. The professor or teaching assistant must be able to obtain the project from GitHub on a Windows computer that has never run it and reproduce the demonstrated functionality by following the README.

- Specify the supported and tested Python version and maintain a `requirements.txt` with tested dependency versions.
- Provide a credential-free `.env.example`. Document external API requirements and potential costs.
- Document virtual environment creation and provide exact Windows PowerShell commands for installation and launch.
- Use relative project paths and include required resources or reproducible setup instructions.
- Ensure local diagnostics inspect the computer running the application.
- Handle missing dependencies, missing API credentials, network failures, and unsupported environments gracefully.
- Include repeatable test scenarios with expected outcomes. Verify a clean installation and launch before final delivery.
- Consider a clearly labeled offline or mock testing mode for use without paid API access. Always label simulated AI responses and diagnostics as simulated.
- Document how to reproduce the results reported in the final research paper.

## Implementation milestones

1. Project setup and basic Streamlit interface.
2. LLM API integration.
3. Diagnostic conversation behavior.
4. Conversation memory.
5. RAG knowledge base and retrieval.
6. Source citations, interactive troubleshooting steps, the General Troubleshooting category, dynamic reclassification, and improved retrieval relevance.
7. First AI-selected, consent-based, read-only local diagnostic tool.
8. Additional read-only diagnostic tools.
9. Session reports, escalation guidance, and basic optional local chat history using SQLite. Support viewing, resuming, and deleting saved sessions, and exclude local database files from Git. Prioritize reports and escalation if persistent history threatens application stability.
10. Comprehensive testing, security review, bug fixes, and reproducibility on a separate Windows computer.

Complete and verify each milestone before moving on. After reporting the milestone, wait for the project owner's approval before proceeding to the next one. Obtain the owner's approval before committing or pushing changes.

### Release checkpoints

Keep existing release tags on their approved commits and retain these release checkpoints.

| Tag | Checkpoint |
| --- | --- |
| `v1.0` | Initial implementation |
| `v2.0` | Partial enhancement |
| `v3.0` | Full enhancement |
| `v3.1` | Testing and validation |

## Final prototype acceptance targets

These are targets to verify during evaluation.

- Launch successfully on a separate Windows computer using the documented instructions.
- Support all five specialized categories and General Troubleshooting, and conduct meaningful diagnostic conversations.
- Retrieve relevant technical documentation and display supporting sources.
- Provide safe, actionable troubleshooting guidance.
- Demonstrate at least one real diagnostic tool selected by the AI. Implement additional tools if feasible.
- Summarize troubleshooting sessions and recommend safe escalation for unresolved problems.
- Evaluate the prototype against at least ten predefined troubleshooting scenarios. Aim for guidance that is both relevant and safe in at least eight out of ten scenarios.

## Development and milestone handoff

The project owner has limited programming experience and needs to explain the implementation during the technical walkthrough.

- Keep code simple, readable, and modular. Use descriptive function and variable names, comment logic that is difficult to follow, and avoid unnecessary abstractions and dependencies.
- Explain important technical decisions, files, and functions in beginner-friendly language.
- Preserve working behavior as features are added. Test new and affected existing functionality, fix discovered errors before declaring a milestone complete, and report only verified behavior as working.
- Keep the README accurate as the application and its setup instructions evolve.

### Milestone report

- A summary of implemented functionality.
- The files created or modified.
- An explanation of important code and functions.
- The commands required to run the application.
- The tests performed and their results.
- Known limitations or unresolved issues.
- The suggested next milestone.
