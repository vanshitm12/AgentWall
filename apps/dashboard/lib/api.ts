const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchAPI(path: string, options?: RequestInit) {
  const response = await fetch(`${API_URL}/api/v1${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}
