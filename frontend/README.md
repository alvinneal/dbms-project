# Aero Charter frontend

React and Vite UI for the Charter Aircraft Rental API. Start the API from the repository
root first; its default development address is `http://localhost:8001`.

## Run locally

```powershell
npm install
npm run dev
```

Open the Vite URL shown in the terminal (usually `http://localhost:5173`). Vite proxies
requests from `/api` to `http://127.0.0.1:8001` and strips the `/api` prefix. To use another
API base URL, set `VITE_API_URL` in a frontend `.env` file; the value should be the API base
path or URL without a trailing slash. For example, `VITE_API_URL=http://localhost:8001`.

## Available scripts

```powershell
npm run dev      # start the development server
npm run build    # create the production bundle in dist/
npm run preview  # serve the production bundle locally
npm run lint     # run ESLint
```

The UI supports customer and operator sign-in. Operators manage their fleet, maintenance,
pilots, and view flights in the Operator Desk. Customers search aircraft, make bookings,
record payments, and manage their trips.
