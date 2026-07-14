# The job read-back demo: jobs -> sessions -> export.
# Rendered by docs/tapes/render.sh, which seeds a demo ledger and sets $HOME.
Output "docs/images/gmlw-usage.gif"

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

Sleep 800ms
Type "gmlw jobs" Sleep 400ms Enter
Sleep 1800ms
Type "gmlw sessions REFACTOR-42" Sleep 400ms Enter
Sleep 1800ms
Type "gmlw export REFACTOR-42" Sleep 400ms Enter
Sleep 4s
