FROM freqtradeorg/freqtrade:stable

USER root
WORKDIR /freqtrade
COPY --chown=freqtrade:freqtrade config.json.template /freqtrade/config.json.template
COPY --chown=freqtrade:freqtrade scripts/render_config.py /freqtrade/scripts/render_config.py
COPY --chown=freqtrade:freqtrade scripts/docker-entrypoint.sh /freqtrade/scripts/docker-entrypoint.sh
RUN chmod 755 /freqtrade/scripts/docker-entrypoint.sh
USER freqtrade
ENTRYPOINT ["/freqtrade/scripts/docker-entrypoint.sh"]
CMD ["trade", "--config", "/freqtrade/user_data/config.json", "--strategy", "TitanAI"]
