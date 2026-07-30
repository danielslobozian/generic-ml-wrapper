# The concepts demo: what gmlw's built-in help explains about itself.
# Rendered by docs/tapes/render.sh, which sets $HOME (no ledger/git needed for this one).
Output "docs/images/gmlw-help.gif"

Set Shell "bash"
Set FontSize 18
Set Width 1200
Set Height 480
Set Padding 22
Set Theme "Catppuccin Mocha"

Hide
Type "export PS1='\033[38;5;208m❯\033[0m '" Enter
Type "cd ~" Enter
Type "clear" Enter
Show

Sleep 800ms
Type "gmlw help" Sleep 400ms Enter
Sleep 2200ms
Type "gmlw help job-vs-workflow" Sleep 400ms Enter
Sleep 4s
