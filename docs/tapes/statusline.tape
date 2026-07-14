# The status line demo: what the wrapper renders into the client's status bar.
# Rendered by docs/tapes/render.sh, which seeds a demo ledger + git repo and sets $HOME.
Output "docs/images/gmlw-statusline.gif"

Set Shell "bash"
Set FontSize 18
Set Width 1200
Set Height 360
Set Padding 22
Set Theme "Catppuccin Mocha"

Hide
Type "export PS1='\033[38;5;208m❯\033[0m '" Enter
Type "cd ${GMLW_DEMO_REPO}" Enter
Type "export GMLW_JOB=REFACTOR-42 GMLW_SESSION=REFACTOR-42_003" Enter
Type `payload='{"model":{"display_name":"Opus 4.8"},"workspace":{"current_dir":"'$PWD'"},"context_window":{"used_percentage":41},"cost":{"total_cost_usd":0.3901}}'` Enter
Type "clear" Enter
Show

Sleep 800ms
Type "# what the wrapper renders into your client's status bar, live:" Sleep 300ms Enter
Type `echo "$payload" | gmlw statusline` Sleep 400ms Enter
Sleep 4s
