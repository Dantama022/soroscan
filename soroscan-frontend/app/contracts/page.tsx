"use client";

import * as React from "react";
import { Card } from "@/components/terminal/Card";
import { Button } from "@/components/terminal/Button";
import { ContractTable } from "./components/ContractTable";
import { RegisterModal } from "./components/RegisterModal";
import { DeleteConfirmModal } from "./components/DeleteConfirmModal";
import {
  listContracts,
  registerContract,
  deleteContract,
} from "@/components/ingest/contract-graphql";
import type { Contract, ContractFormData } from "@/components/ingest/contract-types";
import { useOnboarding } from "@/context/OnboardingContext";

export default function ContractsPage() {
  const { startOnboarding, isActive } = useOnboarding();
  const [contracts, setContracts] = React.useState<Contract[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isRegisterModalOpen, setIsRegisterModalOpen] = React.useState(false);
  const [deleteTarget, setDeleteTarget] = React.useState<Contract | null>(null);
  const [isDeleting, setIsDeleting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [showFavoritesOnly, setShowFavoritesOnly] = React.useState(false);

  const loadContracts = React.useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await listContracts();
      setContracts(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load contracts");
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadContracts();
  }, [loadContracts]);

  const handleRegister = async (data: ContractFormData) => {
    await registerContract(data);
    await loadContracts();
  };

  const handleDeleteClick = (id: string) => {
    const contract = contracts.find((c) => c.id === id);
    if (contract) {
      setDeleteTarget(contract);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;

    setIsDeleting(true);
    try {
      await deleteContract(deleteTarget.id);
      await loadContracts();
      setDeleteTarget(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete contract");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="min-h-screen bg-terminal-black p-4 sm:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl sm:text-3xl font-terminal-mono text-terminal-green mb-2">
              [CONTRACT_REGISTRY]
            </h1>
            <p className="text-terminal-gray font-terminal-mono text-sm">
              Manage tracked contracts and event monitoring
            </p>
          </div>
          <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
            <Button
              variant={showFavoritesOnly ? "primary" : "secondary"}
              onClick={() => setShowFavoritesOnly(!showFavoritesOnly)}
              className="w-full sm:w-auto"
            >
              {showFavoritesOnly ? "Show All" : "Show Favorites"}
            </Button>
            <Button
              variant="primary"
              onClick={() => setIsRegisterModalOpen(true)}
              className="w-full sm:w-auto"
            >
              Register Contract
            </Button>
          </div>
        </div>

        {error && (
          <Card>
            <div className="p-4 border border-terminal-danger bg-terminal-danger/10 text-terminal-danger">
              {error}
            </div>
          </Card>
        )}

        <Card title="TRACKED_CONTRACTS">
          {isLoading ? (
            <div className="text-center py-12 text-terminal-gray font-terminal-mono">
              LOADING...
            </div>
          ) : (
            <ContractTable
                contracts={contracts}
                onDelete={handleDeleteClick}
                onRegister={() => setIsRegisterModalOpen(true)}
                showFavoritesOnly={showFavoritesOnly}
              />
          )}
        </Card>

        <RegisterModal
          isOpen={isRegisterModalOpen}
          onClose={() => setIsRegisterModalOpen(false)}
          onSubmit={handleRegister}
        />

        <DeleteConfirmModal
          isOpen={!!deleteTarget}
          contractName={deleteTarget?.name ?? ""}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteTarget(null)}
          isDeleting={isDeleting}
        />
      </div>
    </div>
  );
}
