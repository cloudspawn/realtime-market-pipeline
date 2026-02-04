"""
Airflow DAG for dbt transformations.

Runs dbt models every 10 minutes to transform raw data into analytics-ready tables.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

# dbt commands with writable paths
DBT_PROJECT_DIR = "/opt/airflow/dbt"
DBT_PROFILES_DIR = "/opt/airflow/dbt"
DBT_TARGET_DIR = "/tmp/dbt_target"
DBT_LOG_DIR = "/tmp/dbt_logs"

dbt_run_cmd = f"""
    mkdir -p {DBT_TARGET_DIR} {DBT_LOG_DIR} && \
    cd {DBT_PROJECT_DIR} && \
    dbt run --profiles-dir {DBT_PROFILES_DIR} --target-path {DBT_TARGET_DIR} --log-path {DBT_LOG_DIR}
"""

dbt_test_cmd = f"""
    mkdir -p {DBT_TARGET_DIR} {DBT_LOG_DIR} && \
    cd {DBT_PROJECT_DIR} && \
    dbt test --profiles-dir {DBT_PROFILES_DIR} --target-path {DBT_TARGET_DIR} --log-path {DBT_LOG_DIR}
"""

with DAG(
    dag_id="dbt_market_pipeline",
    default_args=default_args,
    description="Run dbt transformations for market data",
    schedule_interval=timedelta(minutes=10),
    start_date=datetime(2026, 2, 1),
    catchup=False,
    tags=["dbt", "market-data"],
) as dag:

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=dbt_run_cmd,
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=dbt_test_cmd,
    )

    dbt_run >> dbt_test