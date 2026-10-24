

def calcular_centralidade_grau_local(pontos_alagamento, densidade_norm):
  qtd_norm = min(len(pontos_alagamento) / 20, 1)
  centralidade = (qtd_norm * 0.60) + (densidade_norm * 0.40)
  return float(min(centralidade, 1.0))