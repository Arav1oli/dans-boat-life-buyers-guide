import { PGlite } from "@electric-sql/pglite";
import { PGLiteSocketServer } from "@electric-sql/pglite-socket";
import { pgcrypto } from "@electric-sql/pglite/contrib/pgcrypto";

const db = await PGlite.create({
  dataDir: process.env.PGLITE_DATA_DIR || "memory://",
  extensions: { pgcrypto },
});
const server = new PGLiteSocketServer({
  db,
  host: "127.0.0.1",
  port: Number(process.env.PGLITE_PORT || 55432),
});

await server.start();
console.log(`PGlite PostgreSQL wire server listening on 127.0.0.1:${process.env.PGLITE_PORT || 55432}`);

const stop = async () => {
  await server.stop();
  await db.close();
  process.exit(0);
};
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
