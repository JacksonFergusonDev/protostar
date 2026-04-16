Output docs/assets/demo_wizard.gif

Source demo/_shared.tape

# --- Setup (Hidden) ---
Hide
Type@1ms "rm -rf tmp_wizard && mkdir tmp_wizard && cd tmp_wizard" Enter
Type@1ms "clear" Enter
Sleep 1s
Show
# ----------------------

Sleep 300ms
Type "protostar init"
Sleep 400ms
Enter
Sleep 2s

# "Select the components..."
Space # Selects Python
Sleep 700ms

Down 4
Space # Selects LaTeX
Sleep 700ms

Down 2
Space # Selects Astrophysics
Sleep 700ms

Down 10
Space # Selects mypy
Sleep 700ms

Down 1
Space # Selects pytest

Sleep 2s

Enter # Submit

Sleep 2.5s

Type "tree -a -I '.git|.venv'"
Sleep 200ms
Enter

Sleep 3s

Type "bat pyproject.toml"
Sleep 200ms
Enter

Sleep 2s
Down 15
Sleep 1.5s
Down 18
Sleep 3s
