import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App.jsx";

// Entry point: plugs the App component into the empty div of index.html
// StrictMode only runs in development, it warns about unsafe patterns
createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
