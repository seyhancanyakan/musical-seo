"use client";

import { useEffect, useState } from "react";
import { adminGrantCredits, listAdminUsers, type AdminUser } from "@/lib/api";
import { useLocale, pick } from "@/lib/locale";
import styles from "./page.module.css";
import { formatDate } from "./utils";

type RoleFilter = "all" | "artist" | "curator";

const T = {
  tr: {
    filters: {
      all: "Tümü",
      artist: "Sanatçı",
      curator: "Kurator",
    } as Record<RoleFilter, string>,
    roles: {
      artist: "Sanatçı",
      curator: "Kurator",
      admin: "Admin",
    } as Record<AdminUser["role"], string>,
    loading: "Yükleniyor...",
    empty: "Kullanıcı yok.",
    columns: {
      id: "ID",
      name: "Ad",
      email: "E-posta",
      role: "Rol",
      credits: "Kredi",
      pro: "Pro Bitişi",
      created: "Kayıt Tarihi",
      referral: "Referans Kodu",
      action: "Kredi Yükle",
    },
    amountPlaceholder: "Miktar",
    grantBtn: "Yükle",
    grantingBtn: "...",
  },
  en: {
    filters: {
      all: "All",
      artist: "Artist",
      curator: "Curator",
    } as Record<RoleFilter, string>,
    roles: {
      artist: "Artist",
      curator: "Curator",
      admin: "Admin",
    } as Record<AdminUser["role"], string>,
    loading: "Loading...",
    empty: "No users.",
    columns: {
      id: "ID",
      name: "Name",
      email: "Email",
      role: "Role",
      credits: "Credits",
      pro: "Pro Until",
      created: "Signed Up",
      referral: "Referral Code",
      action: "Grant Credits",
    },
    amountPlaceholder: "Amount",
    grantBtn: "Grant",
    grantingBtn: "...",
  },
} as const;

const ROLE_BADGE: Record<AdminUser["role"], string> = {
  artist: "badgeArtist",
  curator: "badgeCurator",
  admin: "badgeAdmin",
};

/** Admin: kullanicilar listesi — rol filtresi + satir ici hizli kredi yukleme. */
export default function UsersTab() {
  const { locale } = useLocale();
  const t = pick(T, locale);

  const [roleFilter, setRoleFilter] = useState<RoleFilter>("all");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [amounts, setAmounts] = useState<Record<number, string>>({});
  const [busyId, setBusyId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    listAdminUsers(roleFilter === "all" ? undefined : roleFilter).then((data) => {
      if (cancelled) return;
      setUsers(data ?? []);
      setIsLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [roleFilter]);

  async function grantCredits(id: number) {
    const amount = Number(amounts[id]);
    if (!amount) return;
    setBusyId(id);
    const updated = await adminGrantCredits(id, amount);
    if (updated) {
      setUsers((prev) =>
        prev.map((u) => (u.id === id ? { ...u, credits: updated.credits } : u))
      );
      setAmounts((prev) => ({ ...prev, [id]: "" }));
    }
    setBusyId(null);
  }

  const filterKeys: RoleFilter[] = ["all", "artist", "curator"];

  return (
    <div>
      <div className={styles.filters}>
        {filterKeys.map((key) => (
          <button
            key={key}
            type="button"
            className={
              roleFilter === key
                ? `${styles.filterBtn} ${styles.filterActive}`
                : styles.filterBtn
            }
            onClick={() => setRoleFilter(key)}
          >
            {t.filters[key]}
          </button>
        ))}
      </div>

      {isLoading && <div className={styles.loading}>{t.loading}</div>}

      {!isLoading && users.length === 0 && <div className={styles.empty}>{t.empty}</div>}

      {!isLoading && users.length > 0 && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>{t.columns.id}</th>
                <th>{t.columns.name}</th>
                <th>{t.columns.email}</th>
                <th>{t.columns.role}</th>
                <th className={styles.num}>{t.columns.credits}</th>
                <th>{t.columns.pro}</th>
                <th>{t.columns.created}</th>
                <th>{t.columns.referral}</th>
                <th>{t.columns.action}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isBusy = busyId === u.id;
                return (
                  <tr key={u.id}>
                    <td className={styles.sub}>#{u.id}</td>
                    <td className={styles.name}>{u.name}</td>
                    <td>
                      <a className={styles.email} href={`mailto:${u.email}`}>
                        {u.email}
                      </a>
                    </td>
                    <td>
                      <span className={`${styles.badge} ${styles[ROLE_BADGE[u.role]]}`}>
                        {t.roles[u.role]}
                      </span>
                    </td>
                    <td className={styles.num}>{u.credits}</td>
                    <td>
                      {u.pro_until ? (
                        <span className={`${styles.badge} ${styles.badgeApproved}`}>
                          {formatDate(u.pro_until)}
                        </span>
                      ) : (
                        <span className={styles.dash}>—</span>
                      )}
                    </td>
                    <td className={styles.sub}>{formatDate(u.created_at)}</td>
                    <td className={styles.sub}>{u.referral_code ?? "—"}</td>
                    <td>
                      <div className={styles.inlineForm}>
                        <input
                          className={styles.inlineInput}
                          type="number"
                          placeholder={t.amountPlaceholder}
                          value={amounts[u.id] ?? ""}
                          onChange={(e) =>
                            setAmounts((prev) => ({ ...prev, [u.id]: e.target.value }))
                          }
                        />
                        <button
                          type="button"
                          className={`${styles.act} ${styles.actApprove}`}
                          onClick={() => grantCredits(u.id)}
                          disabled={isBusy || !amounts[u.id]}
                        >
                          {isBusy ? t.grantingBtn : t.grantBtn}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
