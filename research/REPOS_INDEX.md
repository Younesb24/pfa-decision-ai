# Olist — Index des repos GitHub de référence

> Document de contexte pour le PFA "Outils IA pour l'aide à la décision"
> Dernière revue : mai 2026

## Stratégie : lecture + copy-paste chirurgical, pas fork

## Pipeline repos (dbt + star schema)
- [longNguyen010203/ECommerce-ELT-Pipeline](https://github.com/longNguyen010203/ECommerce-ELT-Pipeline) — staging/marts patterns, sources.yml
- [rtmagar/ecommerce-elt-pipeline](https://github.com/rtmagar/ecommerce-elt-pipeline) — data contracts JSON, incremental MERGE
- [tahatuzel/olist-batch-processing-etl](https://github.com/tahatuzel/olist-batch-processing-etl) — Snowflake DDL star schema

## ML repos (late delivery + forecast)
- [rismawidiya/Final-Project-Olist](https://github.com/rismawidiya/Final-Project-Olist) — feature engineering for late delivery classifier
- [Alexandre987/Late_Shipment_Prediction_Olist](https://github.com/Alexandre987/Late_Shipment_Prediction_Olist) — SMOTE/ADASYN for imbalanced classes
- [RahulNenavath/Olist-Ecommerce-TimeSeries-Forecasting](https://github.com/RahulNenavath/Olist-Ecommerce-TimeSeries-Forecasting) — temporal features for Prophet

## NLP repos (review sentiment)
- [rajtulluri/Olist-business-analysis](https://github.com/rajtulluri/Olist-business-analysis) — remove_emoji + PT preprocessing
- [ThiagoPanini/sentimentor](https://github.com/ThiagoPanini/sentimentor) — pre-trained sentiment on Olist PT

## Text-to-SQL (runtime dependency)
- [vanna-ai/vanna](https://github.com/vanna-ai/vanna) — **Recommended**: Claude Sonnet native, FastAPI integration, schema-aware
- [arunpshankar/LLM-Text-to-SQL-Architectures](https://github.com/arunpshankar/LLM-Text-to-SQL-Architectures) — 5 architecture patterns (cite in report)

## Rule: cite in rapport "inspiré de [repo X], adapté pour [raison Y]"
