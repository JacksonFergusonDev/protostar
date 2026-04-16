Output docs/assets/demo_headless.gif

Source demo/_shared.tape

# --- Setup (Hidden) ---
Hide
Type@1ms "rm -rf tmp_headless && mkdir tmp_headless && cd tmp_headless" Enter
Sleep 1s
Type@1ms "clear" Enter
Sleep 200ms
Show
# ----------------------

Sleep 300ms
Type "protostar init --python --scientific --pytest --markdownlint"
Sleep 400ms
Enter

Sleep 2s

Type "tree -a -I '.git|.venv'"
Sleep 200ms
Enter

Sleep 2s

Type "bat pyproject.toml"
Sleep 200ms
Enter

Sleep 2s
Down 15
Sleep 2s
Down 15
Sleep 3s
