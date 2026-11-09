import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import App from './App.tsx';

beforeEach(() => {
  Object.defineProperty(window, 'fetch', {
    writable: true,
    value: jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
          tick: 0,
          agents: {},
          casualties: {},
          buildings: {},
          grid_cells: [],
          temporal_constraint: {
            type: 'rescue_count',
            target_count: 2,
            deadline_cycles: 20,
            rescued_count: 1,
            cycles_remaining: 20,
          },
          ended: false,
          success: null,
        }),
      })
    ),
  });

  class MockWebSocket {
    onopen: (() => void) | null = null;
    onclose: (() => void) | null = null;
    onerror: (() => void) | null = null;
    onmessage: ((event: MessageEvent) => void) | null = null;

    constructor(_url: string) {}
    close() {}
  }

  Object.defineProperty(window, 'WebSocket', {
    writable: true,
    value: MockWebSocket,
  });
});

test('renders SARSim control console', async () => {
  render(<App />);
  await waitFor(() => {
    expect(screen.getByText(/SARSim Control Console/i)).toBeInTheDocument();
  });
  expect(screen.getByText(/Load Authored Scenario/i).closest('details')).not.toHaveAttribute('open');
  expect(screen.getByText(/Action Script/i).closest('details')).not.toHaveAttribute('open');
  expect(screen.getByRole('heading', { name: 'Constraints' })).toBeInTheDocument();
  await waitFor(() => {
    expect(screen.getByRole('status')).toHaveTextContent(/Rescue target: 2 casualties/i);
    expect(screen.getByRole('status')).toHaveTextContent(/Rescued: 1/i);
  });
  expect(screen.getByText(/Simulation: Paused/i)).toBeInTheDocument();
  expect(screen.getByText(/WebSocket: Disconnected/i)).toBeInTheDocument();
  expect(screen.getByRole('option', { name: 'Dev Scenario' })).toBeInTheDocument();
});
