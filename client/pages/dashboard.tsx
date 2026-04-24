"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { supabase } from "@/lib/supabase-client";
import {
  Search,
  LayoutDashboard,
  TrendingUp,
  Star,
  Settings,
  ChevronRight,
  ChevronLeft,
  ChevronUp,
  ChevronDown,
  Moon,
  Sun,
} from "lucide-react";
import { exchangeBadgeClasses, formatCurrency, formatPrice, withPlaceholder } from "@/lib/ipo-utils";
import { IPO, SortColumn, SortDirection } from "@/lib/types";
import type { User } from "@supabase/supabase-js";

interface IPOResponseRow {
  cik?: string | number;
  ticker?: string;
  company_name?: string;
  exchange?: string;
  shares_offered?: string | number;
  share_price?: string | number;
  estimated_ipo_date?: string;
  latest_filing_type?: string;
  market_cap?: string | number;
  logo_url?: string | null;
}

const ITEMS_PER_PAGE_OPTIONS = [10, 25, 50];

const sidebarItems = [
  { label: "Dashboard", href: "/", icon: LayoutDashboard },
  { label: "All IPOs", href: "/dashboard", icon: TrendingUp, active: true },
  { label: "Watchlist", href: "/watchlist", icon: Star },
  { label: "Settings", href: "#", icon: Settings },
];

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

export default function Dashboard() {
  const router = useRouter();
  const [ipos, setIpos] = useState<IPO[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [starred, setStarred] = useState<Set<string>>(new Set());
  const [starLoading, setStarLoading] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [darkMode, setDarkMode] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("theme");
    const isDark = stored === "dark" || (!stored && window.matchMedia("(prefers-color-scheme: dark)").matches);
    setDarkMode(isDark);
    document.documentElement.classList.toggle("dark", isDark);
  }, []);

  const toggleDarkMode = () => {
    const next = !darkMode;
    setDarkMode(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("theme", next ? "dark" : "light");
  };

  // Sorting
  const [sortColumn, setSortColumn] = useState<SortColumn | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>(null);

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(25);

  const handleSort = (col: SortColumn) => {
    if (sortColumn === col) {
      if (sortDirection === "asc") setSortDirection("desc");
      else if (sortDirection === "desc") { setSortColumn(null); setSortDirection(null); }
    } else {
      setSortColumn(col);
      setSortDirection("asc");
    }
    setCurrentPage(1);
  };

  const sortedIpos = React.useMemo(() => {
    if (!sortColumn || !sortDirection) return ipos;
    return [...ipos].sort((a, b) => {
      let aVal: string | number = "";
      let bVal: string | number = "";
      if (sortColumn === "name") { aVal = a.companyName; bVal = b.companyName; }
      else if (sortColumn === "exchange") { aVal = a.exchange; bVal = b.exchange; }
      else if (sortColumn === "price") { aVal = parseFloat(a.sharePrice) || 0; bVal = parseFloat(b.sharePrice) || 0; }
      else if (sortColumn === "shares") { aVal = parseFloat(a.sharesOffered.replace(/,/g, "")) || 0; bVal = parseFloat(b.sharesOffered.replace(/,/g, "")) || 0; }
      else if (sortColumn === "raise") { aVal = parseFloat(a.raiseAmount) || 0; bVal = parseFloat(b.raiseAmount) || 0; }
      else if (sortColumn === "date") { aVal = a.estimatedIpoDate; bVal = b.estimatedIpoDate; }
      if (typeof aVal === "string") {
        return sortDirection === "asc" ? aVal.localeCompare(bVal as string) : (bVal as string).localeCompare(aVal);
      }
      return sortDirection === "asc" ? aVal - (bVal as number) : (bVal as number) - aVal;
    });
  }, [ipos, sortColumn, sortDirection]);

  const filteredIpos = searchQuery
    ? sortedIpos.filter(
        (ipo) =>
          ipo.companyName.toLowerCase().includes(searchQuery.toLowerCase()) ||
          ipo.ticker.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : sortedIpos;

  const totalItems = filteredIpos.length;
  const totalPages = Math.ceil(totalItems / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = Math.min(startIndex + itemsPerPage, totalItems);
  const paginatedIpos = filteredIpos.slice(startIndex, endIndex);

  useEffect(() => { setCurrentPage(1); }, [searchQuery, sortColumn, sortDirection, itemsPerPage]);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const { data } = await supabase.auth.getUser();
        const currentUser = data.user;
        setUser(currentUser);

        const res = await fetch("https://ipo-api.theipostreet.workers.dev/api/public?all=true", { cache: "no-store" });
        const json = await res.json();
        if (!res.ok || !Array.isArray(json.rows)) throw new Error(json.error || "Unexpected response");

        const mapped: IPO[] = (json.rows as IPOResponseRow[]).map((r) => ({
          cik: String(r.cik ?? ""),
          ticker: r.ticker ?? "",
          companyName: r.company_name ?? "",
          exchange: r.exchange ?? "",
          sharesOffered: typeof r.shares_offered === "number" ? r.shares_offered.toLocaleString() : typeof r.shares_offered === "string" ? r.shares_offered : "",
          sharePrice: typeof r.share_price === "string" ? r.share_price : typeof r.share_price === "number" ? r.share_price.toString() : "",
          estimatedIpoDate: r.estimated_ipo_date ?? "",
          latestFilingType: r.latest_filing_type ?? "",
          raiseAmount: typeof r.market_cap === "number" ? r.market_cap.toString() : typeof r.market_cap === "string" ? r.market_cap : "",
          logoUrl: r.logo_url ?? null,
          rank: 0,
        }));
        setIpos(mapped);

        if (currentUser) {
          const { data: watchlist } = await supabase.from("watchlist").select("cik").eq("user_id", currentUser.id);
          setStarred(new Set(watchlist?.map((row) => row.cik) ?? []));
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load IPOs");
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, []);

  const toggleStar = async (cik: string) => {
    if (!user) { router.push("/login"); return; }
    if (starLoading === cik) return;
    setStarLoading(cik);
    try {
      if (starred.has(cik)) {
        await supabase.from("watchlist").delete().eq("user_id", user.id).eq("cik", cik);
        setStarred((prev) => { const next = new Set(prev); next.delete(cik); return next; });
      } else {
        await supabase.from("watchlist").insert([{ user_id: user.id, cik }]);
        setStarred((prev) => new Set(prev).add(cik));
      }
    } finally {
      setStarLoading(null);
    }
  };

  const SortIcon = ({ col }: { col: SortColumn }) => {
    if (sortColumn !== col) return <ChevronUp className="w-3 h-3 text-gray-300 opacity-0 group-hover:opacity-100" />;
    return sortDirection === "asc"
      ? <ChevronUp className="w-3 h-3 text-blue-500" />
      : <ChevronDown className="w-3 h-3 text-blue-500" />;
  };

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-gray-950 overflow-hidden font-sans">
      {/* Sidebar */}
      <aside className={`flex flex-col bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 transition-all duration-300 ${sidebarCollapsed ? "w-16" : "w-56"} shrink-0`}>
        {/* Logo */}
        <div className="flex items-center gap-3 px-4 py-5 border-b border-gray-100 dark:border-gray-800">
          <img src="/logo.png" alt="Logo" className="w-8 h-8 object-contain shrink-0" />
          {!sidebarCollapsed && <span className="font-bold text-gray-900 dark:text-white text-base truncate">IPO Street</span>}
        </div>

        {/* Nav items */}
        <nav className="flex-1 py-4 space-y-1 px-2 overflow-y-auto">
          {sidebarItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.label}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors group ${
                  item.active
                    ? "bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
                    : "text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-white"
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                {!sidebarCollapsed && <span className="truncate">{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Dark mode toggle */}
        <div className={`border-t border-gray-100 dark:border-gray-800 px-2 py-2 ${sidebarCollapsed ? "flex justify-center" : ""}`}>
          {sidebarCollapsed ? (
            <button
              onClick={toggleDarkMode}
              title={darkMode ? "Switch to light mode" : "Switch to dark mode"}
              className="p-2 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
            >
              {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
          ) : (
            <div className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
              <div className="flex items-center gap-3 text-sm font-medium text-gray-600 dark:text-gray-400">
                {darkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
                <span>Dark Mode</span>
              </div>
              <label className="relative inline-flex items-center cursor-pointer select-none">
                <input type="checkbox" className="sr-only peer" checked={darkMode} onChange={toggleDarkMode} />
                <div className="w-8 h-4 bg-gray-200 peer-focus:ring-2 peer-focus:ring-blue-300 dark:bg-gray-700 rounded-full peer peer-checked:bg-blue-600 transition-colors" />
                <div className="absolute left-0.5 top-0.5 bg-white w-3 h-3 rounded-full transition-transform peer-checked:translate-x-4" />
              </label>
            </div>
          )}
        </div>

        {/* Collapse toggle */}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="flex items-center justify-center gap-2 px-4 py-3 border-t border-gray-100 dark:border-gray-800 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xs transition-colors"
        >
          {sidebarCollapsed ? <ChevronRight className="w-4 h-4" /> : <><ChevronLeft className="w-4 h-4" /><span>Collapse</span></>}
        </button>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex items-center justify-between px-6 py-4 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 shrink-0">
          <div>
            <div className="flex items-center gap-1.5 text-xs text-gray-400 dark:text-gray-500 mb-0.5">
              <Link href="/" className="hover:text-gray-600 dark:hover:text-gray-300">Home</Link>
              <ChevronRight className="w-3 h-3" />
              <span className="text-gray-600 dark:text-gray-300">All Upcoming IPOs</span>
            </div>
            <h1 className="text-xl font-semibold text-gray-900 dark:text-white">All Upcoming IPOs</h1>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
              <input
                type="text"
                placeholder="Search company or ticker..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 pr-4 py-2 text-sm bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-700 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-900 w-64 caret-auto select-text"
              />
            </div>
            {user ? (
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-semibold shrink-0">
                {user.email?.[0]?.toUpperCase() ?? "U"}
              </div>
            ) : (
              <Link href="/login" className="text-sm font-medium text-blue-600 hover:text-blue-700 dark:text-blue-400">
                Sign In
              </Link>
            )}
          </div>
        </header>

        {/* Table area */}
        <main className="flex-1 overflow-auto p-6">
          {error && <div className="text-sm text-red-500 mb-4">Error: {error}</div>}

          <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead className="border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50">
                  <tr>
                    <th className="px-4 py-3 w-10"></th>
                    <th
                      className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 text-left whitespace-nowrap cursor-pointer hover:text-gray-800 dark:hover:text-gray-200 group"
                      onClick={() => handleSort("name")}
                    >
                      <div className="flex items-center gap-1">Company <SortIcon col="name" /></div>
                    </th>
                    <th
                      className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 text-left whitespace-nowrap cursor-pointer hover:text-gray-800 dark:hover:text-gray-200 group"
                      onClick={() => handleSort("exchange")}
                    >
                      <div className="flex items-center gap-1">Exchange <SortIcon col="exchange" /></div>
                    </th>
                    <th
                      className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 text-right whitespace-nowrap cursor-pointer hover:text-gray-800 dark:hover:text-gray-200 group"
                      onClick={() => handleSort("price")}
                    >
                      <div className="flex items-center justify-end gap-1">Price <SortIcon col="price" /></div>
                    </th>
                    <th
                      className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 text-right whitespace-nowrap cursor-pointer hover:text-gray-800 dark:hover:text-gray-200 group"
                      onClick={() => handleSort("shares")}
                    >
                      <div className="flex items-center justify-end gap-1">Shares <SortIcon col="shares" /></div>
                    </th>
                    <th
                      className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 text-right whitespace-nowrap cursor-pointer hover:text-gray-800 dark:hover:text-gray-200 group"
                      onClick={() => handleSort("raise")}
                    >
                      <div className="flex items-center justify-end gap-1">Raise <SortIcon col="raise" /></div>
                    </th>
                    <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 text-left whitespace-nowrap">
                      Filing
                    </th>
                    <th
                      className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 text-right whitespace-nowrap cursor-pointer hover:text-gray-800 dark:hover:text-gray-200 group"
                      onClick={() => handleSort("date")}
                    >
                      <div className="flex items-center justify-end gap-1">Est. IPO <SortIcon col="date" /></div>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                  {loading
                    ? Array.from({ length: 10 }).map((_, idx) => (
                        <tr key={idx} className="animate-pulse">
                          <td className="px-4 py-4"><div className="w-4 h-4 bg-gray-100 dark:bg-[#1c1e2c] rounded" /></td>
                          <td className="px-4 py-4"><div className="w-36 h-4 bg-gray-100 dark:bg-[#1c1e2c] rounded" /></td>
                          <td className="px-4 py-4"><div className="w-20 h-5 bg-gray-100 dark:bg-[#1c1e2c] rounded-full" /></td>
                          <td className="px-4 py-4 text-right"><div className="w-16 h-4 bg-gray-100 dark:bg-[#1c1e2c] rounded ml-auto" /></td>
                          <td className="px-4 py-4 text-right"><div className="w-20 h-4 bg-gray-100 dark:bg-[#1c1e2c] rounded ml-auto" /></td>
                          <td className="px-4 py-4 text-right"><div className="w-24 h-4 bg-gray-100 dark:bg-[#252840] rounded ml-auto" /></td>
                          <td className="px-4 py-4"><div className="w-12 h-5 bg-gray-100 dark:bg-[#1c1e2c] rounded" /></td>
                          <td className="px-4 py-4 text-right"><div className="w-20 h-4 bg-gray-100 dark:bg-[#1c1e2c] rounded ml-auto" /></td>
                        </tr>
                      ))
                    : paginatedIpos.map((ipo) => (
                        <tr
                          key={ipo.cik}
                          onClick={() => router.push(`/company/${ipo.cik}`)}
                          className="hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer transition-colors"
                        >
                          <td className="px-4 py-4 text-center align-middle">
                            <button
                              onClick={(e) => { e.stopPropagation(); toggleStar(ipo.cik); }}
                              disabled={starLoading === ipo.cik}
                              className="disabled:opacity-40 transition-transform"
                              aria-label="Toggle Watchlist"
                            >
                              {starred.has(ipo.cik) ? (
                                <Star className="w-4 h-4 text-yellow-400 fill-yellow-400" />
                              ) : (
                                <Star className="w-4 h-4 text-gray-300 dark:text-gray-600 hover:text-gray-400" />
                              )}
                            </button>
                          </td>
                          <td className="px-4 py-4 align-middle">
                            <div className="flex flex-col leading-tight">
                              <span className="text-sm font-semibold text-gray-900 dark:text-white">{ipo.companyName}</span>
                              {ipo.ticker && <span className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{ipo.ticker}</span>}
                            </div>
                          </td>
                          <td className="px-4 py-4 align-middle">
                            <span className={`inline-block px-2.5 py-1 rounded-full text-xs font-semibold whitespace-nowrap ${exchangeBadgeClasses(ipo.exchange)}`}>
                              {ipo.exchange || "—"}
                            </span>
                          </td>
                          <td className="px-4 py-4 text-sm text-right text-gray-700 dark:text-gray-300 align-middle font-medium whitespace-nowrap">
                            {formatPrice(ipo.sharePrice)}
                          </td>
                          <td className="px-4 py-4 text-sm text-right text-gray-700 dark:text-gray-300 align-middle font-medium">
                            {withPlaceholder(ipo.sharesOffered)}
                          </td>
                          <td className="px-4 py-4 text-sm text-right align-middle font-semibold">
                            {ipo.raiseAmount && ipo.raiseAmount.trim() !== "" ? (
                              <span className="text-gray-900 dark:text-white">{formatCurrency(ipo.raiseAmount)}</span>
                            ) : (
                              <span className="text-gray-400 italic font-normal">—</span>
                            )}
                          </td>
                          <td className="px-4 py-4 align-middle">
                            {ipo.latestFilingType ? (
                              <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300">
                                {ipo.latestFilingType}
                              </span>
                            ) : (
                              <span className="text-gray-400 text-xs">—</span>
                            )}
                          </td>
                          <td className={`px-4 py-4 text-sm text-right align-middle whitespace-nowrap ${getDateColorClass(ipo.estimatedIpoDate)}`}>
                            {withPlaceholder(ipo.estimatedIpoDate)}
                          </td>
                        </tr>
                      ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {!loading && totalItems > 0 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 dark:border-gray-800 bg-white dark:bg-gray-900">
                <div className="flex items-center gap-3 text-sm text-gray-500 dark:text-gray-400">
                  <span>Rows per page:</span>
                  <select
                    value={itemsPerPage}
                    onChange={(e) => setItemsPerPage(Number(e.target.value))}
                    className="text-sm border border-gray-200 dark:border-gray-700 rounded-md px-2 py-1 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 focus:outline-none"
                  >
                    {ITEMS_PER_PAGE_OPTIONS.map((n) => <option key={n} value={n}>{n}</option>)}
                  </select>
                  <span>{startIndex + 1}–{endIndex} of {totalItems}</span>
                </div>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    disabled={currentPage === 1}
                    className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  >
                    <ChevronLeft className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                  </button>
                  {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                    const page = totalPages <= 7 ? i + 1 : currentPage <= 4 ? i + 1 : currentPage + i - 3;
                    if (page < 1 || page > totalPages) return null;
                    return (
                      <button
                        key={page}
                        onClick={() => setCurrentPage(page)}
                        className={`w-8 h-8 text-sm rounded-md transition-colors ${
                          currentPage === page
                            ? "bg-blue-600 text-white font-semibold"
                            : "text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
                        }`}
                      >
                        {page}
                      </button>
                    );
                  })}
                  <button
                    onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    disabled={currentPage === totalPages}
                    className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  >
                    <ChevronRight className="w-4 h-4 text-gray-600 dark:text-gray-400" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
