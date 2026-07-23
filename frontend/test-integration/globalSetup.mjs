import { spawn } from "node:child_process"
import { existsSync } from "node:fs"
import { resolve } from "node:path"

const HEALTH_URL = "http://127.0.0.1:8031/health"

async function waitForServer(process, output) {
  for (let attempt = 0; attempt < 150; attempt += 1) {
    if (process.exitCode !== null) {
      throw new Error(`FastAPI integration server exited early. ${output.join("")}`)
    }
    try {
      const response = await fetch(HEALTH_URL)
      if (response.ok) return
    } catch {
      // The server is still starting.
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 200))
  }
  throw new Error(`FastAPI integration server did not become ready. ${output.join("")}`)
}

export default async function setup() {
  const projectRoot = resolve(process.cwd(), "..")
  const localPython = resolve(projectRoot, ".venv", "Scripts", "python.exe")
  const python = existsSync(localPython) ? localPython : "python"
  const output = []
  const server = spawn(
    python,
    ["-m", "uvicorn", "tests.integration_app:app", "--host", "127.0.0.1", "--port", "8031"],
    {
      cwd: projectRoot,
      env: { ...process.env, PYTHONDONTWRITEBYTECODE: "1" },
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    },
  )
  server.stdout.on("data", (chunk) => output.push(chunk.toString()))
  server.stderr.on("data", (chunk) => output.push(chunk.toString()))
  try {
    await waitForServer(server, output)
  } catch (error) {
    if (server.exitCode === null) server.kill()
    throw error
  }

  return async () => {
    if (server.exitCode === null) {
      server.kill()
      await new Promise((resolveExit) => {
        server.once("exit", resolveExit)
        setTimeout(resolveExit, 2000)
      })
    }
  }
}
