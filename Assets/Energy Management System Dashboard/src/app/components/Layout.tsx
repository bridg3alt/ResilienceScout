import { useState } from "react";
import { Sidebar } from "./Sidebar";
import { Dashboard } from "./Dashboard";
import { Analytics } from "./Analytics";

const Configuration = () => (
  <div className="p-6">
    <h1 className="text-3xl mb-4">Configuration</h1>
    <p className="text-muted-foreground">System configuration and device management coming soon...</p>
  </div>
);

const Reports = () => (
  <div className="p-6">
    <h1 className="text-3xl mb-4">Reports</h1>
    <p className="text-muted-foreground">Generate and export energy reports coming soon...</p>
  </div>
);

const Settings = () => (
  <div className="p-6">
    <h1 className="text-3xl mb-4">Settings & Profile</h1>
    <p className="text-muted-foreground">User preferences and profile settings coming soon...</p>
  </div>
);

export function Layout() {
  const [currentPage, setCurrentPage] = useState("dashboard");

  const renderContent = () => {
    switch (currentPage) {
      case "dashboard":
        return <Dashboard />;
      case "analytics":
        return <Analytics />;
      case "configuration":
        return <Configuration />;
      case "reports":
        return <Reports />;
      case "settings":
        return <Settings />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <div className="flex h-screen bg-background">
      <div className="flex-shrink-0">
        <Sidebar currentPage={currentPage} onPageChange={setCurrentPage} />
      </div>
      <main className="flex-1 overflow-auto">
        {renderContent()}
      </main>
    </div>
  );
}