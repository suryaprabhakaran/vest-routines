Run the Vest routines by dispatching the GitHub Actions workflow.

Execute: gh workflow run vest.yml --repo suryaprabhakaran/vest-routines

This triggers all three routines in the cloud immediately:
- NSE/Global market tracker (also runs automatically Sundays 8pm Brussels)
- Job scanner (also runs automatically daily Mon-Sat + Sundays as part of the full run)
- Signal logger — logs 1-2 high-conviction signals + scores prior ones (also runs automatically Sundays 8pm Brussels)

Confirm dispatch succeeded.
