# Future work (honest production roadmap)

These are deliberately NOT claimed as done. Ordered by value.

1. **Human labeling operations.** The 300-image benchmark needs 2+ reviewers,
   adjudication rules, and inter-rater agreement reporting before it is a real
   benchmark. The labeling app exists; the operations do not.
2. **Online feature store.** Risk features are batch-computed. A Feast or
   BigQuery-based feature store would serve them at event time.
3. **Model monitoring.** Track prediction drift, label drift, and calibration
   decay on a schedule; alert on degradation.
4. **Dataflow comparison.** A short-lived Dataflow job vs the Pub/Sub direct
   path, with measured cost and latency. Not a streaming job left running.
5. **Vision cascade tuning.** Measure the full cascade (OpenCV -> AutoML ->
   Gemini) on the human-labeled benchmark: cost per image vs quality.
6. **Agent confidence calibration.** The 0.6 escalation threshold is
   provisional. Collect human judgments on agent decisions and calibrate.
7. **Load testing.** Replay at 10x and 100x to find the real bottlenecks.
8. **PII review.** Olist customer IDs are pseudonymous but the pipeline should
   pass a formal privacy review before touching real customer data.
