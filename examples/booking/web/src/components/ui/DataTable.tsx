/**
 * DataTable — TanStack Table v8 wrapper.
 *
 * Sticky header, dense rows, optional row click → onRowClick (drawer
 * mount), keyboard-focusable rows, mono-faced ids for scanability,
 * loading skeletons that match column widths, and a Vertex-shape
 * "no results" empty body. Sort + global filter + sticky-first-column
 * supported via the same flags every callsite uses.
 *
 * The column shape is the same `ColumnDef<T>` TanStack ships — no
 * adapter layer. The component is just the chrome.
 */
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { useState, type ReactNode } from "react";
import { ChevronDown, ChevronUp, ChevronsUpDown } from "lucide-react";

import { cn } from "@/lib/cn";

interface Props<T> {
  data: T[];
  columns: ColumnDef<T, unknown>[];
  loading?: boolean;
  loadingRows?: number;
  emptyState?: ReactNode;
  onRowClick?: (row: T) => void;
  /** Stable row key, defaults to row index. */
  getRowId?: (row: T, index: number) => string;
  /** Highlight this row id (e.g. the row whose drawer is open). */
  activeRowId?: string | null;
  /** Full-width container className. */
  className?: string;
  /** Apply a global filter; uses TanStack's built-in. */
  globalFilter?: string;
}

export function DataTable<T>({
  data,
  columns,
  loading,
  loadingRows = 6,
  emptyState,
  onRowClick,
  getRowId,
  activeRowId,
  className,
  globalFilter,
}: Props<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter: globalFilter ?? "" },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getRowId: getRowId ? (row, index) => getRowId(row, index) : undefined,
    enableSortingRemoval: true,
  });

  const headers = table.getHeaderGroups();
  const rows = table.getRowModel().rows;
  const showEmpty = !loading && rows.length === 0;

  return (
    <div className={cn("relative overflow-auto rounded-lg border border-coal-500 bg-coal-700/60", className)}>
      <table className="w-full border-collapse text-[13px] text-coal-50">
        <thead className="sticky top-0 z-10 bg-coal-700/95 backdrop-blur-sm">
          {headers.map((hg) => (
            <tr key={hg.id} className="border-b border-coal-500">
              {hg.headers.map((header) => {
                const canSort = header.column.getCanSort();
                const sort = header.column.getIsSorted();
                return (
                  <th
                    key={header.id}
                    className={cn(
                      "h-9 px-3 text-left text-[11px] uppercase tracking-wide text-coal-200 font-medium",
                      canSort && "cursor-pointer select-none hover:text-coal-50",
                    )}
                    style={{ width: header.getSize() === 150 ? undefined : header.getSize() }}
                    onClick={canSort ? header.column.getToggleSortingHandler() : undefined}
                  >
                    <span className="inline-flex items-center gap-1">
                      {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                      {canSort && (
                        sort === "asc" ? <ChevronUp className="size-3" />
                        : sort === "desc" ? <ChevronDown className="size-3" />
                        : <ChevronsUpDown className="size-3 opacity-40" />
                      )}
                    </span>
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {loading && Array.from({ length: loadingRows }).map((_, i) => (
            <tr key={`sk-${i}`} className="border-b border-coal-500/60">
              {table.getAllLeafColumns().map((c) => (
                <td key={c.id} className="h-10 px-3">
                  <div className="h-3 w-2/3 rounded bg-coal-500 animate-pulse-soft" />
                </td>
              ))}
            </tr>
          ))}
          {!loading && rows.map((row) => {
            const id = row.id;
            const active = activeRowId && activeRowId === id;
            const clickable = !!onRowClick;
            return (
              <tr
                key={id}
                tabIndex={clickable ? 0 : undefined}
                onClick={clickable ? () => onRowClick(row.original) : undefined}
                onKeyDown={
                  clickable
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onRowClick(row.original);
                        }
                      }
                    : undefined
                }
                className={cn(
                  "border-b border-coal-500/60 transition-colors",
                  clickable && "cursor-pointer hover:bg-coal-500/40 focus:bg-coal-500/40 outline-none",
                  active && "bg-coal-500/60 hover:bg-coal-500/60",
                )}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="h-10 px-3 align-middle text-coal-100">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            );
          })}
          {showEmpty && (
            <tr>
              <td colSpan={table.getAllLeafColumns().length} className="p-0">
                {emptyState ?? <DefaultEmpty />}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function DefaultEmpty() {
  return (
    <div className="py-12 text-center text-[12.5px] text-coal-200">
      No results.
    </div>
  );
}
