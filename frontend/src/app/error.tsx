"use client";
import { ErrorState } from "@/components/workspace/Shared";
export default function ErrorPage({
  retry,
}: {
  error: Error;
  retry: () => void;
}) {
  return (
    <ErrorState
      message="The analysis could not be displayed. Retry to reload this view."
      retry={retry}
    />
  );
}
