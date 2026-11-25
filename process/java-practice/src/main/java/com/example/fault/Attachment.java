package com.example.fault;

public class Attachment {

    private final User uploader;
    private final String uploaderNameSnapshot;

    public Attachment(User uploader, String uploaderNameSnapshot) {
        this.uploader = uploader;
        this.uploaderNameSnapshot = uploaderNameSnapshot;
    }

    public String getUploaderName() {
        return uploader != null ? uploader.getDisplayName() : uploaderNameSnapshot;
    }
}