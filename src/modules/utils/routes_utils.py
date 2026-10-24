def serializar_json(obj):

    if isinstance(obj, dict):
        return {
            k: serializar_json(v)
            for k, v in obj.items()
        }

    if isinstance(obj, list):
        return [
            serializar_json(v)
            for v in obj
        ]

    try:
        import pandas as pd

        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()

    except Exception:
        pass

    try:
        import numpy as np

        if isinstance(obj, np.integer):
            return int(obj)

        if isinstance(obj, np.floating):
            return float(obj)

        if isinstance(obj, np.ndarray):
            return obj.tolist()

    except Exception:
        pass

    return obj