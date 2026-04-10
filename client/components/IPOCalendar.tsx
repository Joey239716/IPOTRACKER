import React, { useMemo } from "react";
import { IPO } from "@/lib/types";

interface Props {
  ipos: IPO[];
}

const DAY_LABELS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

export function IPOCalendar({ ipos }: Props) {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth();

  const monthLabel = now.toLocaleDateString("en-US", { month: "long", year: "numeric" });

  // Set of day-of-month numbers that have an IPO
  const ipoDays = useMemo(() => {
    const days = new Set<number>();
    ipos.forEach((ipo) => {
      if (!ipo.estimatedIpoDate) return;
      const d = new Date(ipo.estimatedIpoDate + "T00:00:00");
      if (d.getFullYear() === year && d.getMonth() === month) {
        days.add(d.getDate());
      }
    });
    return days;
  }, [ipos, year, month]);

  // Build grid: leading empty cells + days of month
  const firstDayOfWeek = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const today = now.getDate();

  const cells: (number | null)[] = [
    ...Array(firstDayOfWeek).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];

  // Pad to complete last row
  while (cells.length % 7 !== 0) cells.push(null);

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-5">
      <h2 className="text-sm font-semibold text-slate-900 mb-4">{monthLabel}</h2>

      {/* Day labels */}
      <div className="grid grid-cols-7 mb-1">
        {DAY_LABELS.map((d) => (
          <div key={d} className="text-center text-[10px] font-semibold text-slate-400 uppercase">
            {d}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-y-1">
        {cells.map((day, i) => {
          if (!day) return <div key={i} />;
          const isToday = day === today;
          const hasIpo = ipoDays.has(day);

          return (
            <div key={i} className="flex flex-col items-center py-0.5">
              <span
                className={`w-7 h-7 flex items-center justify-center rounded-full text-xs font-medium
                  ${isToday
                    ? "bg-slate-900 text-white"
                    : "text-slate-600"
                  }`}
              >
                {day}
              </span>
              {hasIpo ? (
                <span className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-0.5" />
              ) : (
                <span className="w-1.5 h-1.5 mt-0.5" />
              )}
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-1.5 mt-3 pt-3 border-t border-gray-100">
        <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
        <span className="text-[10px] text-slate-400">IPO scheduled</span>
      </div>
    </div>
  );
}
