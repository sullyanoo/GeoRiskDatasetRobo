def calcular_penalizacao_baixa_vegetacao(percentual_verde):
    """
    Penalização estrutural suave.
    """

    if percentual_verde < 0.03:
        return 0.20

    if percentual_verde < 0.08:
        return 0.12

    if percentual_verde < 0.15:
        return 0.06

    if percentual_verde < 0.25:
        return 0.03

    return 0.0


def classificar_risco(probabilidade, percentual_verde=None):
    """
    Classificação final interpretativa.
    """

    if probabilidade >= 0.60:
        return "Alto Risco"

    if probabilidade >= 0.33:
        return "Médio Risco"

    if percentual_verde is not None and percentual_verde < 0.08:
        return "Médio Risco"

    return "Baixo Risco"


def calcular_penalizacao_baixa_vegetacao(percentual_verde):
  """Penalização estrutural suave por déficit extremo de cobertura vegetal."""
  if percentual_verde < 0.03:
    return 0.20
  if percentual_verde < 0.08:
    return 0.12
  if percentual_verde < 0.15:
    return 0.06
  if percentual_verde < 0.25:
    return 0.03
  return 0.0


def classificar_risco(probabilidade, percentual_verde=None):
  """Classificação final interpretativa baseada nos limiares operacionais."""
  if probabilidade >= 0.60:
    return "Alto Risco"
  if probabilidade >= 0.33:
    return "Médio Risco"
  if percentual_verde is not None and percentual_verde < 0.08:
    return "Médio Risco"
  return "Baixo Risco"