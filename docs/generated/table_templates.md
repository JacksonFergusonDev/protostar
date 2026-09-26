| Template | Description | Default tier | Invocation | Dependencies |
| :--- | :--- | :--- | :--- | :--- |
| `api` | FastAPI web application scaffold with Uvicorn and Pydantic | Production | `protostar init --template api` | `fastapi`, `uvicorn`, `pydantic-settings` |
| `astro` | Astrophysics and astronomy data analysis scaffold with Astropy | Workbench | `protostar init --template astro` | `numpy`, `scipy`, `pandas`, `matplotlib`, `astropy`, `astroquery`, `specutils` |
| `cli` | Rich & Typer command-line application | Production | `protostar init --template cli` | `typer`, `rich` |
| `lib` | Reusable Python library (pip-installable, PEP 561 typed) | Production | `protostar init --template lib` | *None* |
| `ml` | Machine learning & data science scaffold with PyTorch and Jupyter | Workbench | `protostar init --template ml` | `torch`, `scikit-learn`, `pandas`, `numpy`, `matplotlib`, `tqdm` |
