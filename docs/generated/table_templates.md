| Template | Description | Invocation | Dependencies |
| :--- | :--- | :--- | :--- |
| `api` | FastAPI web application scaffold with Uvicorn and Pydantic | `protostar init --template api` | `fastapi`, `uvicorn`, `pydantic-settings` |
| `astro` | Astrophysics and astronomy data analysis scaffold with Astropy | `protostar init --template astro` | `numpy`, `scipy`, `pandas`, `matplotlib`, `astropy`, `astroquery`, `photutils`, `specutils` |
| `cli` | Rich & Typer command-line application | `protostar init --template cli` | `typer`, `rich` |
| `lib` | Reusable Python library (pip-installable, PEP 561 typed) | `protostar init --template lib` | *None* |
| `ml` | Machine learning & data science scaffold with PyTorch and Jupyter | `protostar init --template ml` | `torch`, `scikit-learn`, `pandas`, `numpy`, `matplotlib`, `tqdm` |
