// components/IPOTableMobile.tsx

import React from "react";
import { StarIcon as StarIconOutline } from "@heroicons/react/24/outline";
import { StarIcon as StarIconSolid } from "@heroicons/react/24/solid";
import { useRouter } from "next/navigation";
import { IPO } from "@/lib/types";
import { exchangeBadgeClasses, formatCurrency, formatIpoDate, withPlaceholder } from "@/lib/ipo-utils";

interface Props {
  loading: boolean;
  sortedIpos: IPO[];
  starred: Set<string>;
  starLoading: string | null;
  onToggleStar: (cik: string) => void;
}

const getDateColorClass = (date: string): string => {
  if (!date) return "";
  
  const ipoDate = new Date(date);
  const today = new Date();
  const diffDays = Math.ceil((ipoDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  
  if (diffDays <= 7) return "text-green-600 dark:text-green-400 font-semibold";
  if (diffDays <= 30) return "text-blue-600 dark:text-blue-400 font-medium";
  if (diffDays <= 90) return "text-gray-700 dark:text-gray-300";
  return "text-gray-500 dark:text-gray-400";
};

export const IPOTableMobile: React.FC<Props> = ({
  loading,
  sortedIpos,
  starred,
  starLoading,
  onToggleStar
}) => {
  const router = useRouter();

  const handleCardClick = (cik: string, e: React.MouseEvent) => {
    // Don't navigate if clicking on interactive elements
    const target = e.target as HTMLElement;
    if (
      target.closest('button') || 
      target.closest('a') ||
      target.closest('[role="button"]')
    ) {
      return;
    }
    router.push(`/company/${cik}`);
  };

  return (
    <div className="sm:hidden rounded-2xl border border-gray-200 dark:border-[#252f3e] bg-white dark:bg-[#161b27] shadow-[0_8px_30px_rgba(0,0,0,0.12)] hover:shadow-[0_12px_40px_rgba(0,0,0,0.18)] transition-shadow duration-300 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 dark:border-[#252f3e] flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">Upcoming IPOs</h2>
        <a href="/dashboard" className="text-sm font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 transition-colors">
          View All
        </a>
      </div>
    <div className="p-4 space-y-4">
      {loading
        ? Array.from({ length: 5 }).map((_, idx) => (
            <div
              key={idx}
              className="p-5 rounded-2xl bg-white dark:bg-[#1c2333] border border-gray-100 dark:border-[#252f3e] shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] animate-pulse"
            >
              <div className="flex items-center gap-3 mb-3">
                <div className="w-5 h-5 bg-slate-100 dark:bg-[#1c1e2c] rounded" />
                <div className="w-10 h-10 bg-slate-200 dark:bg-[#252840] rounded-lg" />
                <div className="flex-1 h-4 bg-slate-100 dark:bg-[#1c1e2c] rounded" />
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                {["Price", "Shares", "Raise", "Est. IPO", "Exchange"].map(
                  (label, i) => (
                    <React.Fragment key={i}>
                      <div className="font-medium text-slate-500">{label}</div>
                      <div className="h-4 bg-slate-100 dark:bg-[#1c1e2c] rounded" />
                    </React.Fragment>
                  )
                )}
              </div>
            </div>
          ))
        : sortedIpos.map((ipo, index) => (
            <div
              key={ipo.cik}
              onClick={(e) => handleCardClick(ipo.cik, e)}
              className="p-5 rounded-2xl bg-white dark:bg-[#1c2333] border border-gray-100 dark:border-[#252f3e] shadow-[0_4px_20px_-4px_rgba(0,0,0,0.05)] hover:shadow-[0_8px_30px_-4px_rgba(0,0,0,0.1)] hover:-translate-y-1 transition-all duration-300 cursor-pointer"
              style={{
                animation: `slideIn 0.4s ease-out ${index * 0.05}s both`
              }}
            >
              {/* Main Content */}
              <div className="flex items-center gap-3 mb-4">
                <div
                  className="flex flex-col truncate leading-tight flex-1"
                  title={ipo.companyName}
                >
                  <span className="text-base font-bold text-slate-900 dark:text-slate-100 truncate">
                    {ipo.companyName}
                  </span>
                  {ipo.ticker && ipo.ticker.trim() !== "" && (
                    <span className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                      {ipo.ticker}
                    </span>
                  )}
                </div>
                <button
                  onClick={() => onToggleStar(ipo.cik)}
                  disabled={starLoading === ipo.cik}
                  aria-label="Toggle Watchlist"
                  className="disabled:opacity-40 hover:scale-110 transition-transform duration-200 shrink-0"
                >
                  {starred.has(ipo.cik) ? (
                    <StarIconSolid className="w-5 h-5 text-yellow-400 drop-shadow-sm" />
                  ) : (
                    <StarIconOutline className="w-5 h-5 text-gray-400" />
                  )}
                </button>
              </div>

              {/* Data Grid */}
              <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                <div className="font-semibold text-slate-500 dark:text-slate-400">Price</div>
                <div className="text-right font-medium text-slate-700 dark:text-slate-300">
                  {withPlaceholder(ipo.sharePrice)}
                </div>

                <div className="font-semibold text-slate-500 dark:text-slate-400">Shares</div>
                <div className="text-right font-medium text-slate-700 dark:text-slate-300">
                  {withPlaceholder(ipo.sharesOffered)}
                </div>

                <div className="font-semibold text-slate-500 dark:text-slate-400">Raise</div>
                <div className="text-right font-semibold">
                  {ipo.raiseAmount && ipo.raiseAmount.trim() !== "" ? (
                    <span className="text-slate-900 dark:text-slate-100">
                      {formatCurrency(ipo.raiseAmount)}
                    </span>
                  ) : (
                    <span className="text-slate-400 dark:text-slate-500 italic font-normal">
                      Not available
                    </span>
                  )}
                </div>

                <div className="font-semibold text-slate-500 dark:text-slate-400">Est. IPO</div>
                <div className="text-right text-slate-700 dark:text-slate-300">
                  {formatIpoDate(ipo.estimatedIpoDate)}
                </div>

                <div className="font-semibold text-slate-500 dark:text-slate-400">Exchange</div>
                <div className="text-right">
                  <span
                    className={`inline-block px-3 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${exchangeBadgeClasses(
                      ipo.exchange
                    )}`}
                  >
                    {ipo.exchange || "Unknown"}
                  </span>
                </div>
              </div>
            </div>
          ))}

      <style jsx>{`
        @keyframes slideIn {
          from {
            opacity: 0;
            transform: translateX(-20px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }
      `}</style>
    </div>
    </div>
  );
};