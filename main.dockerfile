ARG JAVA_VERSION
FROM gcr.io/distroless/java${JAVA_VERSION}-debian12

COPY paper.jar app.jar

WORKDIR /app

CMD ["-jar", "../app.jar"]
