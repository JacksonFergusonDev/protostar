| Preset | CLI Flags | Description | Default Dependencies |
| :--- | :--- | :--- | :--- |
| Scientific | `-s`, `--scientific` | Inject scientific computing dependencies | `numpy`, `matplotlib`, `seaborn`, `pandas`, `scipy`, `ipykernel`, `scikit-learn` |
| Astrophysics | `-a`, `--astro` | Inject astrophysics dependencies | `numpy`, `scipy`, `pandas`, `matplotlib`, `astropy`, `astroquery`, `photutils`, `specutils`, `nbdime` |
| Digital Signal Processing | `-d`, `--dsp` | Inject digital signal processing dependencies | `librosa`, `soundfile`, `mido`, `mutagen`, `pydub` |
| Embedded Hardware | `-e`, `--embedded` | Inject embedded hardware dependencies | `pyserial`, `esptool`, `adafruit-blinka` |
| Machine Learning | `--ml` | Inject machine learning and deep learning dependencies | `torch`, `scikit-learn`, `huggingface_hub`, `tqdm` |
| REST API | `--api` | Inject REST API backend dependencies | `fastapi`, `uvicorn`, `pydantic`, `httpx` |
| CLI Application | `--cli` | Inject CLI application dependencies | `typer`, `rich` |
