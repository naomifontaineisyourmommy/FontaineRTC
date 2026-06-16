import React from "react";
import ReactDOM from "react-dom/client";
import "./styles/global.css";
import App from "./App";
import { ThemeProvider } from "./theme/ThemeProvider";
import { ToastProvider } from "./components/ui";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider>
      <ToastProvider>
        <App />
      </ToastProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
