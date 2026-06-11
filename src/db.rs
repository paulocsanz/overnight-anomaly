use sqlx::postgres::PgPool;

pub async fn init_pool(database_url: &str) -> anyhow::Result<PgPool> {
    let pool = sqlx::postgres::PgPoolOptions::new()
        .max_connections(5)
        .connect(database_url)
        .await?;

    sqlx::query("SELECT 1").execute(&pool).await?;

    Ok(pool)
}

pub async fn run_migrations(pool: &PgPool) -> anyhow::Result<()> {
    sqlx::query(include_str!("../migrations/001_create_tables.sql"))
        .execute(pool)
        .await?;
    Ok(())
}
