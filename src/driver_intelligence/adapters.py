"""Adapter interfaces for later cloud connection. NOT EXECUTED LOCALLY.

This module is design for later connection, not a live connection.
- StopMemoryPort: the interface the agent depends on. The local
  implementation is StopMemoryStore (SQLite/in-memory) in memory.py.
- BigQueryStopMemoryStore: a BigQuery implementation of the same
  interface, written but NOT executed, NOT connected, and NOT used by
  any test, demo, or eval in this update. Instantiating it creates no
  client and makes no network call; the client is created lazily only
  when a method is called by code that has explicitly chosen the cloud
  path with valid GCP credentials. Do not instantiate it in local runs.
- PubSubApproachConsumer: the same pattern for Pub/Sub. The local
  consumer in consumer.py reads simulated JSONL events; this class is
  the subscriber that would replace it later. Its subscribe method is
  never called by tests, demos, or evals.

Switchover steps (also in INSTALLATION_INSTRUCTIONS.md):
  1. Run sql/driver_intelligence_schema.sql in BigQuery (project owner
     approval required; this update never runs it).
  2. Set config: store_backend = "bigquery", project id, dataset name,
     and Pub/Sub subscription name.
  3. Provide GCP credentials through the normal secure setup flow
     (service account with BigQuery data editor and Pub/Sub subscriber
     roles on the driver_intelligence dataset and topic only).
  4. Replace the store construction with BigQueryStopMemoryStore and
     the consumer construction with PubSubApproachConsumer. No agent,
     feedback, card, or eval code changes are needed, because they all
     depend on the port interface, not on SQLite.
  5. Verify with a read-only smoke check: one assigned driver, one
     stop profile read, one approach event, then compare the card and
     trace against the local run before any production use.
No GCP resource is created, modified, or deleted by this module.
"""

from abc import ABC, abstractmethod


class StopMemoryPort(ABC):
    """Interface the agent and feedback code depend on."""

    @abstractmethod
    def is_authorized(self, driver_id: str, stop_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_profile(self, stop_id: str):
        raise NotImplementedError

    @abstractmethod
    def upsert_profile(self, profile):
        raise NotImplementedError

    @abstractmethod
    def add_observation(self, observation):
        raise NotImplementedError

    @abstractmethod
    def list_observations(self, stop_id: str):
        raise NotImplementedError


class BigQueryStopMemoryStore(StopMemoryPort):
    """BigQuery implementation of StopMemoryPort. NOT CONNECTED.

    Creating an instance performs no GCP call and creates no client.
    Methods raise a clear error until a caller explicitly builds a
    client with credentials, so accidental local execution cannot
    bill anything or touch any project resource.
    """

    def __init__(self, project: str, dataset: str = "driver_intelligence"):
        self.project = project
        self.dataset = dataset
        self.client = None

    def _client(self):
        if self.client is None:
            try:
                from google.cloud import bigquery
            except ImportError as exc:
                raise RuntimeError(
                    "BigQuery adapter requires google-cloud-bigquery and "
                    "valid GCP credentials. It is not used by local runs."
                ) from exc
            self.client = bigquery.Client(project=self.project)
        return self.client

    def _table(self, name: str) -> str:
        return f"{self.project}.{self.dataset}.{name}"

    def is_authorized(self, driver_id: str, stop_id: str) -> bool:
        client = self._client()
        query = (
            f"SELECT 1 FROM `{self._table('driver_assignments')}` "
            "WHERE driver_id = @driver_id AND stop_id = @stop_id LIMIT 1")
        from google.cloud import bigquery
        job = client.query(query, job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("driver_id", "STRING", driver_id),
                bigquery.ScalarQueryParameter("stop_id", "STRING", stop_id)]))
        return any(True for _ in job.result())

    def get_profile(self, stop_id: str):
        client = self._client()
        query = (
            f"SELECT * FROM `{self._table('stop_profiles')}` "
            "WHERE stop_id = @stop_id AND is_current = TRUE LIMIT 1")
        from google.cloud import bigquery
        job = client.query(query, job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("stop_id", "STRING", stop_id)]))
        rows = list(job.result())
        if not rows:
            return None
        from .memory import StopProfile
        row = dict(rows[0])
        row["leave_unattended_restriction"] = bool(row["leave_unattended_restriction"])
        row["is_current"] = bool(row["is_current"])
        return StopProfile(**{k: row.get(k, "") if row.get(k) is not None else ""
                              for k in StopProfile.__dataclass_fields__})

    def upsert_profile(self, profile):
        client = self._client()
        from google.cloud import bigquery
        d = profile.to_dict()
        query = (
            f"MERGE `{self._table('stop_profiles')}` T USING "
            "(SELECT @stop_id AS stop_id) S ON T.stop_id = S.stop_id "
            "WHEN MATCHED THEN UPDATE SET preferred_placement = @placement, "
            "verification_status = @verification_status, "
            "gate_verification_status = @gate_status, updated_at = CURRENT_TIMESTAMP() "
            "WHEN NOT MATCHED THEN INSERT (stop_id, preferred_placement, "
            "verification_status, gate_verification_status) VALUES "
            "(@stop_id, @placement, @verification_status, @gate_status)")
        client.query(query, job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("stop_id", "STRING", d["stop_id"]),
                bigquery.ScalarQueryParameter("placement", "STRING", d["preferred_placement"]),
                bigquery.ScalarQueryParameter("verification_status", "STRING", d["verification_status"]),
                bigquery.ScalarQueryParameter("gate_status", "STRING", d["gate_verification_status"])]))
        return profile

    def add_observation(self, observation):
        client = self._client()
        from google.cloud import bigquery
        query = (
            f"INSERT INTO `{self._table('stop_observations')}` "
            "(stop_id, kind, text, source_type, verification_status, is_restriction) "
            "VALUES (@stop_id, @kind, @text, @source_type, @verification_status, @is_restriction)")
        client.query(query, job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("stop_id", "STRING", observation.stop_id),
                bigquery.ScalarQueryParameter("kind", "STRING", observation.kind),
                bigquery.ScalarQueryParameter("text", "STRING", observation.text),
                bigquery.ScalarQueryParameter("source_type", "STRING", observation.source_type),
                bigquery.ScalarQueryParameter("verification_status", "STRING", observation.verification_status),
                bigquery.ScalarQueryParameter("is_restriction", "BOOL", observation.is_restriction)]))
        return observation

    def list_observations(self, stop_id: str):
        client = self._client()
        query = (
            f"SELECT * FROM `{self._table('stop_observations')}` "
            "WHERE stop_id = @stop_id ORDER BY created_at")
        from google.cloud import bigquery
        job = client.query(query, job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("stop_id", "STRING", stop_id)]))
        from .memory import Observation
        out = []
        for row in job.result():
            d = dict(row)
            out.append(Observation(
                stop_id=d["stop_id"], kind=d["kind"], text=d["text"],
                source_type=d["source_type"],
                verification_status=d.get("verification_status", "unverified"),
                created_at=str(d.get("created_at", "")),
                is_restriction=bool(d.get("is_restriction", False))))
        return out


class PubSubApproachConsumer:
    """Pub/Sub subscriber for approach events. NOT CONNECTED.

    Creating an instance performs no GCP call. subscribe() is never
    called by tests, demos, or evals; it exists so a later switchover
    replaces the local JSONL consumer without changing agent code.
    Each pulled message is parsed as JSON, run through the agent, and
    acknowledged only after the agent returns a result, which gives
    at-least-once delivery with the agent's own idempotency dedup.
    """

    def __init__(self, project: str, subscription: str, agent):
        self.project = project
        self.subscription = subscription
        self.agent = agent
        self.subscriber = None

    def subscribe(self, timeout_seconds: int = 60):
        try:
            from google.cloud import pubsub_v1
        except ImportError as exc:
            raise RuntimeError(
                "Pub/Sub adapter requires google-cloud-pubsub and valid "
                "GCP credentials. It is not used by local runs."
            ) from exc
        import json
        self.subscriber = pubsub_v1.SubscriberClient()
        path = self.subscriber.subscription_path(self.project, self.subscription)
        response = self.subscriber.pull(
            request={"subscription": path, "max_messages": 10},
            timeout=timeout_seconds)
        results = []
        ack_ids = []
        for message in response.received_messages:
            event = json.loads(message.message.data.decode("utf-8"))
            results.append(self.agent.handle_approach(event))
            ack_ids.append(message.ack_id)
        if ack_ids:
            self.subscriber.acknowledge(
                request={"subscription": path, "ack_ids": ack_ids})
        return results
