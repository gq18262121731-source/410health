# AI Health IoT Flutter App

## Real-device server setup

This mobile app must connect to the backend service, not the frontend dev server.

Use:

- protocol: `http`
- host: the PC LAN IP, for example `192.168.8.252`
- port: `8000`

Do **not** use:

- `10.0.2.2` on a real phone
- `127.0.0.1`
- `localhost`
- frontend ports `5173`, `5182`
- tool ports `7860`, `7861`, `8090`

## Expected flow

1. Start backend on the PC.
2. Confirm `http://<PC-LAN-IP>:8000/healthz` opens from the phone browser.
3. In the app, open **服务器设置**.
4. Fill `http + <PC-LAN-IP> + 8000`.
5. Tap **测试连接**.
6. Save only after health check passes.

## Notes

- The app stores host, port, and scheme in shared preferences.
- After the endpoint changes, alarm and profile providers are reloaded.
- The server settings screen now blocks common wrong ports such as `5173` and `7860`.
