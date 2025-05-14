import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.jsx';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <div className="flex justify-center items-center min-h-screen bg-gray-100">
      <App />
    </div>
  </StrictMode>
);
