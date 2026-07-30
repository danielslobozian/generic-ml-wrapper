# The interactive menu demo: gmlw tui, a browse-only tour.
# Rendered by docs/tapes/render.sh, which seeds a demo ledger + one workflow and sets $HOME.
# Only read-only browser screens are entered (Job > List, Workflow > List, Config > List) --
# never New/Resume/Run/Create/Edit/the config switchers, which launch a client or write config.
Output "docs/images/gmlw-tui.gif"

Set Shell "bash"
Set FontSize 18
Set Width 1200
Set Height 820
Set Padding 22
Set Theme "Catppuccin Mocha"

Hide
Type "export PS1='\033[38;5;208m❯\033[0m '" Enter
Type "cd ~" Enter
Type "clear" Enter
Show

Sleep 500ms
Type "gmlw tui" Enter
Sleep 1200ms

# Front door: walk the cursor down through Job / Workflow / Config / Rules, then back to Job.
Down
Sleep 400ms
Down
Sleep 400ms
Down
Sleep 400ms
Up
Sleep 300ms
Up
Sleep 300ms
Up
Sleep 300ms

# Job > List — read-only, shows the seeded job.
Enter
Sleep 700ms
Down
Sleep 300ms
Down
Sleep 300ms
Enter
Sleep 900ms
Escape
Sleep 400ms
Escape
Sleep 400ms

# Workflow > List — read-only, shows the seeded workflow.
Down
Sleep 400ms
Enter
Sleep 700ms
Down
Sleep 300ms
Down
Sleep 300ms
Down
Sleep 300ms
Enter
Sleep 900ms
Escape
Sleep 400ms
Escape
Sleep 400ms

# Config > List — read-only, every setting.
Down
Sleep 400ms
Enter
Sleep 700ms
Enter
Sleep 1200ms
Escape
Sleep 400ms
Escape
Sleep 400ms

# Back at the front door — leave.
Escape
Sleep 1500ms
