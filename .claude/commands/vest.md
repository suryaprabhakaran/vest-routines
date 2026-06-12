Run the Vest routines by dispatching the GitHub Actions workflow.

Execute: gh workflow run vest.yml --repo suryaprabhakaran/vest-routines

This triggers all three routines in the cloud:
- NSE/Global market tracker (weekly Sunday 8pm Brussels)
- Job scanner (weekly Sunday 8pm Brussels)
- Signal logger (daily 11pm Brussels) — logs 1-2 high-conviction signals + scores prior ones

Confirm dispatch succeeded.
