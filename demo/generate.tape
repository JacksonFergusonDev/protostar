Output docs/assets/demo_generate.gif

Source demo/_shared.tape

# --- Setup (Hidden) ---
Hide
Type@1ms "rm -rf tmp_gen && mkdir tmp_gen && cd tmp_gen" Enter

Type@1ms "echo '## Core LaTeX files' > .gitignore" Enter
Type@1ms "echo '*.aux' >> .gitignore" Enter
Type@1ms "echo '*.bbl' >> .gitignore" Enter
Type@1ms "echo '*.blg' >> .gitignore" Enter
Type@1ms "echo '*.brf' >> .gitignore" Enter
Type@1ms "echo '*.fls' >> .gitignore" Enter
Type@1ms "echo '*.fdb_latexmk' >> .gitignore" Enter
Type@1ms "echo '*.lof' >> .gitignore" Enter
Type@1ms "echo '*.log' >> .gitignore" Enter
Type@1ms "echo '*.lot' >> .gitignore" Enter
Type@1ms "echo '*.nav' >> .gitignore" Enter
Type@1ms "echo '*.out' >> .gitignore" Enter
Type@1ms "echo '*.snm' >> .gitignore" Enter
Type@1ms "echo '*.synctex.gz' >> .gitignore" Enter
Type@1ms "echo '*.toc' >> .gitignore" Enter
Type@1ms "echo '*.vrb' >> .gitignore" Enter
Type@1ms "echo '' >> .gitignore" Enter
Type@1ms "echo '## Compiled documents' >> .gitignore" Enter
Type@1ms "echo '*.pdf' >> .gitignore" Enter
Type@1ms "echo '*.dvi' >> .gitignore" Enter
Type@1ms "echo '*.ps' >> .gitignore" Enter
Type@1ms "echo '*.xdv' >> .gitignore" Enter

Type@1ms "clear" Enter
Sleep 1s
Show
# ----------------------

Sleep 500ms
Type "protostar generate tex report"
Sleep 300ms
Enter

Sleep 2s

Type "bat report.tex"
Sleep 300ms
Enter
Sleep 3s
Type "q"
Sleep 300ms

Type "protostar generate cpp-class TelemetryIngestor"
Sleep 300ms
Enter

Sleep 2s

Type "tree"
Sleep 300ms
Enter
Sleep 3s

Type "bat TelemetryIngestor.cpp"
Sleep 300ms
Enter
Sleep 3s

Type "bat TelemetryIngestor.hpp"
Sleep 300ms
Enter
Sleep 4s
