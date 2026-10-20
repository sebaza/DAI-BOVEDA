"""Feature Percepción — lectura de agregados de sentimiento de la comunidad UCN.

La Torre SOLO LEE los agregados que produce el worker externo de percepción
(repo Sentiment_Analisys_University). El worker escribe las tablas `percepcion_*`
en la misma BD operacional; aquí se mapean como modelos de SOLO LECTURA y se
sirven al dashboard. La Torre nunca carga torch ni recalcula el índice.
"""
