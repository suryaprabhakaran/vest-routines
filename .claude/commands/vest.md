Run the Vest routines by dispatching the GitHub Actions workflow.

Execute: gh workflow run vest.yml --repo suryaprabhakaran/vest-routines

This triggers all three routines in the cloud, all on the weekly Sunday 8pm Brussels schedule:
- NSE/Global market tracker
- Job scanner
- Signal logger — logs 1-2 high-conviction signals + scores prior ones

Confirm dispatch succeeded.
