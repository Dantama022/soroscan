import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import { ThemeProvider, useTheme } from '@/providers/ThemeProvider';

function ThemeStateProbe() {
  const { theme } = useTheme();
  return <span data-testid="current-theme">{theme}</span>;
}

describe('ThemeToggle', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('renders an accessible toggle button and defaults to system theme inside ThemeProvider', () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
        <ThemeStateProbe />
      </ThemeProvider>,
    );

    const button = screen.getByRole('button', { name: 'Toggle Theme' });
    expect(button).toBeInTheDocument();
    expect(screen.getByTestId('current-theme')).toHaveTextContent('system');
    expect(localStorage.getItem('theme')).toBe('system');
    expect(button.querySelector('svg')).toHaveClass('lucide-monitor');
    expect(document.documentElement).not.toHaveClass('dark');
  });

  it('applies dark class in system mode when prefers-color-scheme is dark', () => {
    (window.matchMedia as jest.Mock).mockImplementationOnce((query: string) => ({
      matches: true,
      media: query,
      onchange: null,
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    }));

    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );

    expect(document.documentElement).toHaveClass('dark');
  });

  it('loads stored theme from localStorage on mount', () => {
    localStorage.setItem('theme', 'dark');

    render(
      <ThemeProvider>
        <ThemeToggle />
        <ThemeStateProbe />
      </ThemeProvider>,
    );

    const button = screen.getByRole('button', { name: 'Toggle Theme' });
    expect(screen.getByTestId('current-theme')).toHaveTextContent('dark');
    expect(button.querySelector('svg')).toHaveClass('lucide-moon');
    expect(document.documentElement).toHaveClass('dark');
  });

  it('cycles through system -> light -> dark -> system on click', () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
        <ThemeStateProbe />
      </ThemeProvider>,
    );

    const button = screen.getByRole('button', { name: 'Toggle Theme' });
    const themeProbe = screen.getByTestId('current-theme');

    // Initial: system
    expect(themeProbe).toHaveTextContent('system');
    expect(button.querySelector('svg')).toHaveClass('lucide-monitor');

    // system -> light
    fireEvent.click(button);
    expect(themeProbe).toHaveTextContent('light');
    expect(localStorage.getItem('theme')).toBe('light');
    expect(document.documentElement).not.toHaveClass('dark');
    expect(button.querySelector('svg')).toHaveClass('lucide-sun');

    // light -> dark
    fireEvent.click(button);
    expect(themeProbe).toHaveTextContent('dark');
    expect(localStorage.getItem('theme')).toBe('dark');
    expect(document.documentElement).toHaveClass('dark');
    expect(button.querySelector('svg')).toHaveClass('lucide-moon');

    // dark -> system
    fireEvent.click(button);
    expect(themeProbe).toHaveTextContent('system');
    expect(localStorage.getItem('theme')).toBe('system');
    expect(document.documentElement).not.toHaveClass('dark');
    expect(button.querySelector('svg')).toHaveClass('lucide-monitor');
  });

  it('renders safely using default context when rendered without ThemeProvider', () => {
    render(<ThemeToggle />);

    const button = screen.getByRole('button', { name: 'Toggle Theme' });
    expect(button.querySelector('svg')).toHaveClass('lucide-monitor');

    expect(() => fireEvent.click(button)).not.toThrow();
    expect(button.querySelector('svg')).toHaveClass('lucide-monitor');
  });
});
