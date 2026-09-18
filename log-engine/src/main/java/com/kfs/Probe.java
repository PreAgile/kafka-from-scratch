package com.kfs;

/** 하네스 검증용 임시 파일. 검증이 끝나면 삭제한다. */
public final class Probe {
    private Probe() {
    }

    public static long now() {
        return System.currentTimeMillis();
    }
}
