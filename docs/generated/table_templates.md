| Template | Description | Invocation | Dependencies |
| :--- | :--- | :--- | :--- |
| `api` | FastAPI web application scaffold with Uvicorn and Pydantic | `protostar init --template api` | `fastapi`, `uvicorn`, `pydantic-settings` |
| `astro` | Astrophysics and astronomy data analysis scaffold with Astropy | `protostar init --template astro` | `numpy`, `scipy`, `pandas`, `matplotlib`, `astropy`, `astroquery`, `photutils`, `specutils`, `nbdime` |
| `cli` | Rich & Typer command-line application | `protostar init --template cli` | `typer`, `rich` |
| `dsp` | Digital signal processing and audio analysis scaffold | `protostar init --template dsp` | `librosa`, `soundfile`, `scipy`, `numpy`, `matplotlib`, `pedalboard` |
| `embedded` | Embedded Python development and microcontroller setup | `protostar init --template embedded` | `pyserial`, `mpremote` |
| `lib` | Reusable Python library (pip-installable, PEP 561 typed) | `protostar init --template lib` | *None* |
| `ml` | Machine learning & data science scaffold with PyTorch and Jupyter | `protostar init --template ml` | `torch`, `scikit-learn`, `pandas`, `numpy`, `matplotlib`, `tqdm` |
