import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { CopyButton } from '@/src/components/CopyButton';

describe('CopyButton', () => {
  const writeTextMock = jest.fn<Promise<void>, [string]>();
  const originalClipboard = navigator.clipboard;
  const originalExecCommand = document.execCommand;

  beforeEach(() => {
    writeTextMock.mockReset();
    writeTextMock.mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: writeTextMock },
    });
    document.execCommand = jest.fn().mockReturnValue(true);
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: originalClipboard,
    });
    document.execCommand = originalExecCommand;
  });

  it('renders an accessible button with copy label and custom className', () => {
    render(<CopyButton text="CABC123" className="custom-btn" />);

    const button = screen.getByRole('button', { name: 'Copy to clipboard' });
    expect(button).toBeInTheDocument();
    expect(button).toHaveAttribute('type', 'button');
    expect(button).toHaveAttribute('title', 'Copy to clipboard');
    expect(button).toHaveClass('custom-btn');
    expect(button.querySelector('svg')).not.toHaveClass('text-green-500');
  });

  it('copies provided text via navigator.clipboard.writeText and shows copied feedback', async () => {
    render(<CopyButton text="C1234567890" />);

    const button = screen.getByRole('button', { name: 'Copy to clipboard' });
    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });

    expect(writeTextMock).toHaveBeenCalledTimes(1);
    expect(writeTextMock).toHaveBeenCalledWith('C1234567890');
    expect(button.querySelector('svg')).toHaveClass('text-green-500');
  });

  it('resets copied feedback after 2000ms', async () => {
    jest.useFakeTimers();
    render(<CopyButton text="reset-test" />);

    const button = screen.getByRole('button', { name: 'Copy to clipboard' });
    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });

    expect(button.querySelector('svg')).toHaveClass('text-green-500');

    act(() => {
      jest.advanceTimersByTime(1999);
    });
    expect(button.querySelector('svg')).toHaveClass('text-green-500');

    act(() => {
      jest.advanceTimersByTime(1);
    });
    expect(button.querySelector('svg')).not.toHaveClass('text-green-500');
  });

  it('falls back to document.execCommand when navigator.clipboard.writeText rejects', async () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    writeTextMock.mockRejectedValueOnce(new Error('Permission denied'));

    render(<CopyButton text="fallback-text" />);

    const button = screen.getByRole('button', { name: 'Copy to clipboard' });
    await act(async () => {
      fireEvent.click(button);
      await Promise.resolve();
    });

    expect(writeTextMock).toHaveBeenCalledWith('fallback-text');
    expect(document.execCommand).toHaveBeenCalledWith('copy');
    expect(document.querySelector('textarea')).not.toBeInTheDocument();
    expect(button.querySelector('svg')).toHaveClass('text-green-500');
    expect(consoleErrorSpy).toHaveBeenCalled();
  });

  it('falls back to document.execCommand when navigator.clipboard is unavailable', () => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: undefined,
    });

    render(<CopyButton text="no-clipboard-api" />);

    const button = screen.getByRole('button', { name: 'Copy to clipboard' });
    fireEvent.click(button);

    expect(document.execCommand).toHaveBeenCalledWith('copy');
    expect(document.querySelector('textarea')).not.toBeInTheDocument();
    expect(button.querySelector('svg')).toHaveClass('text-green-500');
  });
});
