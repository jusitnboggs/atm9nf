# Live Modlist

This file tracks the current mods installed in our customized instance of ATM 9 No Frills. 

If you add, remove, or update any mods, you should document them here or regenerate this list.

To regenerate this list, run the following in PowerShell from the instance root:

```powershell
Get-ChildItem -Path mods -Filter *.jar | Select-Object -ExpandProperty Name > docs/MODLIST_LIVE.md
```
