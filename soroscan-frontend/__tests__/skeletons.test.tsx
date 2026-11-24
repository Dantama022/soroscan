import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import {
  ContractCardSkeleton,
  EventDetailModalSkeleton,
  EventTableSkeleton,
  StatWidgetSkeleton,
} from '@/components/ui/skeletons';

describe('ContractCardSkeleton', () => {
  it('renders without props and exposes accessible loading status', () => {
    const { container } = render(<ContractCardSkeleton />);

    const status = screen.getByRole('status');
    expect(status).toHaveTextContent('Loading contracts…');
    expect(status).toHaveAttribute('aria-live', 'polite');

    // Both responsive placeholder views are hidden from assistive tech.
    const hiddenRegions = container.querySelectorAll('[aria-hidden="true"]');
    expect(hiddenRegions.length).toBeGreaterThanOrEqual(2);

    // Table structure + 5 skeleton rows.
    expect(container.querySelectorAll('tbody tr')).toHaveLength(5);
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0);

    // No misleading interactive controls.
    expect(screen.queryAllByRole('button')).toHaveLength(0);
    expect(screen.queryAllByRole('link')).toHaveLength(0);
    expect(screen.queryAllByRole('textbox')).toHaveLength(0);
  });
});

describe('EventDetailModalSkeleton', () => {
  it('renders modal placeholders, loading status, and wires onClose button', () => {
    const onClose = jest.fn();
    const { container } = render(<EventDetailModalSkeleton onClose={onClose} />);

    const status = screen.getByRole('status');
    expect(status).toHaveTextContent('Loading event details…');
    expect(status).toHaveAttribute('aria-live', 'polite');

    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(10);

    // Only intentional close button is interactive.
    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(1);
    const closeButton = screen.getByRole('button', { name: 'Close modal' });
    fireEvent.click(closeButton);
    expect(onClose).toHaveBeenCalledTimes(1);

    expect(screen.queryAllByRole('link')).toHaveLength(0);
    expect(screen.queryAllByRole('textbox')).toHaveLength(0);
  });
});

describe('EventTableSkeleton', () => {
  it('renders default table placeholders without tags and exposes loading status', () => {
    const { container } = render(<EventTableSkeleton />);

    const status = screen.getByRole('status');
    expect(status).toHaveTextContent('Loading events…');
    expect(status).toHaveAttribute('aria-live', 'polite');

    expect(screen.getByRole('columnheader', { name: 'Contract' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Type' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Ledger' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Time' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Transaction' })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Actions' })).toBeInTheDocument();
    expect(screen.queryByRole('columnheader', { name: 'Tags' })).not.toBeInTheDocument();

    expect(container.querySelectorAll('tbody tr')).toHaveLength(5);
    expect(container.querySelectorAll('.soroscan-event-card')).toHaveLength(5);
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0);

    expect(screen.queryAllByRole('button')).toHaveLength(0);
    expect(screen.queryAllByRole('checkbox')).toHaveLength(0);
  });

  it('renders the Tags column when showTags is true', () => {
    render(<EventTableSkeleton showTags />);

    expect(screen.getByRole('columnheader', { name: 'Tags' })).toBeInTheDocument();
  });
});

describe('StatWidgetSkeleton', () => {
  it('renders 4 cards by default with aria-busy and status announcement', () => {
    const { container } = render(<StatWidgetSkeleton />);

    const status = screen.getByRole('status');
    expect(status).toHaveTextContent('Loading statistics…');
    expect(status).toHaveAttribute('aria-live', 'polite');

    const section = container.querySelector('section[aria-busy="true"]');
    expect(section).toBeInTheDocument();
    expect(section).toHaveAttribute('aria-label', 'Loading statistics');
    expect(section).toHaveClass('lg:grid-cols-4');
    expect(container.querySelectorAll('article')).toHaveLength(4);

    expect(screen.queryAllByRole('button')).toHaveLength(0);
    expect(screen.queryAllByRole('link')).toHaveLength(0);
  });

  it('supports custom count and system layout preset', () => {
    const { container } = render(<StatWidgetSkeleton count={3} layout="system" />);

    const section = container.querySelector('section[aria-busy="true"]');
    expect(section).toHaveClass('md:grid-cols-3');
    expect(section).not.toHaveClass('lg:grid-cols-4');
    expect(container.querySelectorAll('article')).toHaveLength(3);
  });
});
