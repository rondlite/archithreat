# Self-hosting

Purpose: how to run the [archithreat](../src/archithreat/__init__.py) Docker container inside your own trust zone, what to configure, and where the operator's responsibilities start.

## Contents

- [Run the container](#run-the-container)
- [Environment variables](#environment-variables)
- [Sizing](#sizing)
- [TLS termination](#tls-termination)
- [No shipped manifests](#no-shipped-manifests)
- [About the vendored htmx](#about-the-vendored-htmx)

## Run the container

```bash
docker run --rm -p 8000:8000 \
  -e ARCHITHREAT_MAX_UPLOAD_MB=100 \
  -e ARCHITHREAT_RATE_LIMIT_PER_MINUTE=60 \
  ghcr.io/<org>/archithreat:latest
```

The image is multi-stage, runs as UID 1000, exposes port 8000, and has a healthcheck pointed at `/healthz`. There is no database. There is no on-disk persistence of user content. The conversion pipeline runs entirely in memory; this property is enforced by [tests/web/test_no_persistence.py](../tests/web/test_no_persistence.py).

Liveness and readiness endpoints are at `/healthz` and `/readyz`. `/readyz` runs an embedded fixture through the conversion pipeline at every check, so it returns 503 if the core itself is broken, not only if the process is up.

The same FastAPI app is reachable via `archithreat serve` from the CLI when a Python install is preferable to Docker.

## Environment variables

All configuration is environment-driven via Pydantic Settings ([`web/settings.py`](../src/archithreat/web/settings.py)).

| Variable | Default | Meaning |
|---|---|---|
| `ARCHITHREAT_HOST` | `0.0.0.0` | Bind address. |
| `ARCHITHREAT_PORT` | `8000` | Bind port. |
| `ARCHITHREAT_MAX_UPLOAD_MB` | `50` | Hard limit on the `model` and `mapping` form fields combined. Enforced at the streaming layer in [`web/limits.py`](../src/archithreat/web/limits.py). |
| `ARCHITHREAT_REQUEST_TIMEOUT_SECONDS` | `120` | Wall-clock guard around the conversion call. On timeout, returns 504. |
| `ARCHITHREAT_RATE_LIMIT_PER_MINUTE` | `30` | Per-IP rate limit via `slowapi`, in-memory. Set to `0` to disable. |
| `ARCHITHREAT_CORS_ORIGINS` | `""` (none) | Comma-separated list of allowed origins. Empty disables CORS entirely. |
| `ARCHITHREAT_LOG_LEVEL` | `info` | Application log level. Logs include request metadata; they never include user content, mapping content, or output. |
| `ARCHITHREAT_FORWARDED_ALLOW_IPS` | `""` | Trusted upstream proxies for `X-Forwarded-For`. Set to your reverse-proxy IP if you want client IP-based rate limiting to work behind a proxy. |

## Sizing

Per-request memory is roughly **50–200 MB**, dominated by the parsed `lxml` tree and the in-memory output buffer. A 50 MB upload is the configured ceiling; pathological inputs at that ceiling can briefly land toward the upper end. Conversion is **CPU-bound** and synchronous within a request; FastAPI runs the sync handler in a thread pool.

Practical guidance:

- **One uvicorn worker per CPU core** is the typical starting point. Two cores = `--workers 2`. The CPU-bound profile means more workers than cores does not help.
- Memory budget: `workers × 200 MB` covers the headroom. Add OS overhead.
- For a small team using the converter ad-hoc, a single 1-core / 512 MB container is fine.
- For a department-wide endpoint, expect bursts; size for `(workers × 250 MB) + 100 MB` and set the rate limit to a number you can sustain.

The container is stateless. Horizontal scale is N copies behind a load balancer with no shared state. Health checks at `/healthz` keep the orchestrator honest.

## TLS termination

TLS is the operator's responsibility. The container speaks plain HTTP on its bind port. Front it with one of:

- **nginx** or **Caddy** as a reverse proxy on the same host.
- **Traefik** if you are running container orchestration that integrates with it.
- A cloud load balancer (AWS ALB, GCP HTTPS LB, Azure Application Gateway) that terminates TLS and forwards to the container.

If you front it with a reverse proxy, set `ARCHITHREAT_FORWARDED_ALLOW_IPS` to your proxy's IP so the rate limiter sees real client IPs from `X-Forwarded-For` rather than treating every request as coming from the proxy.

## No shipped manifests

There are no Helm charts, no Kubernetes manifests, no docker-compose files in this repository. Operators wire their own. A typical Kubernetes deployment maps cleanly: one Deployment, one Service, one Ingress with TLS. Roughly:

```yaml
# illustrative; not shipped
apiVersion: apps/v1
kind: Deployment
metadata: { name: archithreat }
spec:
  replicas: 2
  selector: { matchLabels: { app: archithreat } }
  template:
    metadata: { labels: { app: archithreat } }
    spec:
      containers:
        - name: archithreat
          image: ghcr.io/<org>/archithreat:latest
          ports: [{ containerPort: 8000 }]
          env:
            - { name: ARCHITHREAT_MAX_UPLOAD_MB, value: "100" }
          readinessProbe: { httpGet: { path: /readyz, port: 8000 } }
          livenessProbe:  { httpGet: { path: /healthz, port: 8000 } }
          resources:
            requests: { cpu: "200m", memory: "256Mi" }
            limits:   { cpu: "1",    memory: "512Mi" }
```

The deliberate decision behind shipping no manifests: operators who run container orchestration can write the above; operators who cannot are better served by the browser app, which needs no infrastructure at all.

## About the vendored htmx

The HTMX library used by the web shell's HTML UI is vendored at [`src/archithreat/web/static/htmx.min.js`](../src/archithreat/web/static/htmx.min.js). The current file is a placeholder; before relying on the HTMX UI in production, vendor a real htmx 1.9.x release into that path so the file matches the script tag in the templates. The JSON API at `/api/v1/*` does not depend on htmx and is unaffected.
